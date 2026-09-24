from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Document
from app.db.research_models import ResearchRun, ResearchRunSource, SourceCoverage
from app.errors import NexusError
from app.research.service import create_run


def test_pins_source_order_versions_and_coverage(db, settings, ready_source):
    first, first_document, _ = ready_source()
    second, second_document, _ = ready_source()
    run = create_run(db, " Compare the proposals ", [second.id, first.id], settings)
    pins = db.scalars(select(ResearchRunSource).order_by(ResearchRunSource.source_order)).all()
    assert run.question == "Compare the proposals"
    assert run.status == "created"
    assert [pin.document_id for pin in pins] == [second_document.id, first_document.id]
    assert [pin.document_version for pin in pins] == [1, 1]
    assert run.retrieval_config["max_sources"] == 5
    assert run.answer_config["max_claims"] == 12
    assert db.scalar(select(func.count()).select_from(SourceCoverage)) == 2

    replacement = Document(
        source_id=first.id,
        version=2,
        status="ready",
        mime_type="application/pdf",
        parser_name="docling",
        parser_version="test",
        normalized_text="New version.",
    )
    db.add(replacement)
    db.flush()
    first.current_document_id = replacement.id
    first.display_name = "Renamed after the run"
    db.commit()
    db.expire_all()
    assert pins[1].document_id == first_document.id
    assert pins[1].display_name == "Research fixture"


@pytest.mark.parametrize(
    "selection,code",
    [
        ([], "SOURCE_SET_TOO_SMALL"),
        ([uuid4()], "SOURCE_SET_TOO_SMALL"),
        ([uuid4() for _ in range(6)], "SOURCE_SET_TOO_LARGE"),
        ([uuid4(), uuid4()], "SOURCE_NOT_FOUND"),
    ],
)
def test_rejects_invalid_source_set_without_creating_run(db, settings, selection, code):
    with pytest.raises(NexusError) as error:
        create_run(db, "Compare", selection, settings)
    assert error.value.code == code
    assert db.scalar(select(func.count()).select_from(ResearchRun)) == 0


def test_rejects_duplicates_and_not_ready_snapshots(db, settings, ready_source):
    first, _, _ = ready_source()
    second, document, _ = ready_source()
    with pytest.raises(NexusError, match="distinct"):
        create_run(db, "Compare", [first.id, first.id], settings)
    document.status = "failed"
    db.commit()
    with pytest.raises(NexusError, match="ready snapshot"):
        create_run(db, "Compare", [first.id, second.id], settings)
    assert db.scalar(select(func.count()).select_from(ResearchRun)) == 0


@pytest.mark.parametrize(
    "options",
    [
        {"mode": "autonomous"},
        {"top_k_per_source": 0},
        {"top_k_per_source": 21},
        {"max_claims": 0},
        {"max_claims": 13},
    ],
)
def test_rejects_unbounded_options(db, settings, ready_source, options):
    sources = [ready_source()[0].id for _ in range(2)]
    with pytest.raises(NexusError):
        create_run(db, "Compare", sources, settings, **options)


def test_coverage_cannot_reference_a_different_run(db, settings, ready_source):
    sources = [ready_source()[0].id for _ in range(2)]
    first = create_run(db, "Compare", sources, settings)
    second = create_run(db, "Compare again", sources, settings)
    pin = db.scalar(select(ResearchRunSource).where(ResearchRunSource.research_run_id == first.id))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(SourceCoverage(research_run_id=second.id, research_run_source_id=pin.id))
        db.flush()


def test_maximum_source_set_is_accepted_and_every_source_is_pinned(db, settings, ready_source):
    ids = [ready_source()[0].id for _ in range(settings.max_research_sources)]
    run = create_run(db, "Compare all five", ids, settings)
    assert (
        db.scalar(
            select(func.count())
            .select_from(ResearchRunSource)
            .where(ResearchRunSource.research_run_id == run.id)
        )
        == 5
    )
    assert db.scalar(select(func.count()).select_from(SourceCoverage)) == 5


def test_source_cannot_pin_another_sources_document(db, settings, ready_source):
    first, first_document, _ = ready_source()
    second, _, _ = ready_source()
    second.current_document_id = first_document.id
    db.commit()
    with pytest.raises(NexusError, match="ready snapshot"):
        create_run(db, "Compare", [first.id, second.id], settings)
    assert db.scalar(select(func.count()).select_from(ResearchRun)) == 0
