from time import perf_counter

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Document
from app.db.research_models import EvidenceItem, ResearchRetrievalResult, SourceCoverage
from app.errors import NexusError
from app.research import retrieval
from app.research.service import create_run


def test_retrieves_each_source_with_one_embedding_and_copies_locators(
    db, settings, ready_source, azure_api
):
    first, _, first_chunks = ready_source()
    second, _, second_chunks = ready_source()
    ready_source(("Unselected confidential document.",))
    run = create_run(db, "Compare", [first.id, second.id], settings, top_k_per_source=1)
    evidence = retrieval.retrieve_evidence(db, run, settings, perf_counter())
    assert [item.chunk_id for item in evidence] == [first_chunks[0].id, second_chunks[0].id]
    assert [item.label for item in evidence] == ["E1", "E2"]
    assert evidence[0].locator_snapshot == first_chunks[0].locator
    assert "page(s) 1" in evidence[0].display_text
    assert not any(item.used for item in evidence)
    assert len(azure_api["calls"]) == 1
    assert azure_api["calls"][0][0].endswith("/embeddings")
    assert run.embedding_tokens == 8
    rows = db.scalars(select(ResearchRetrievalResult)).all()
    assert [row.source_rank for row in rows] == [1, 1]
    assert all(row.selected for row in rows)
    assert run.retrieval_config["embedding_model"] == "text-embedding-3-large"


def test_pinned_search_ignores_later_source_state_and_current_version(
    db, settings, ready_source, azure_api
):
    first, _, original_chunks = ready_source()
    second, _, _ = ready_source()
    run = create_run(db, "Compare", [first.id, second.id], settings)
    newer = Document(
        source_id=first.id,
        version=2,
        status="parsing",
        mime_type="application/pdf",
        parser_name="docling",
        parser_version="test",
    )
    db.add(newer)
    db.flush()
    first.current_document_id = newer.id
    first.status = "parsing"
    db.commit()
    evidence = retrieval.retrieve_evidence(db, run, settings, perf_counter())
    assert {chunk.id for chunk in original_chunks}.issubset({item.chunk_id for item in evidence})


def test_context_budget_is_fair_and_exclusions_are_explicit(db, settings, ready_source, azure_api):
    settings.max_research_context_chars = 40
    first, _, _ = ready_source(("x" * 21, "fits first"))
    second, _, _ = ready_source(("fits second",))
    run = create_run(db, "Compare", [first.id, second.id], settings)
    evidence = retrieval.retrieve_evidence(db, run, settings, perf_counter())
    assert [item.excerpt for item in evidence] == ["fits first", "fits second"]
    assert run.retrieval_config["context_chars"] <= 40
    coverage = db.scalars(select(SourceCoverage)).all()
    assert sum(row.context_limited for row in coverage) == 1
    assert all(row.selected_chunk_count == 1 for row in coverage)


def test_no_fitting_passage_is_not_called_irrelevant(db, settings, ready_source, azure_api):
    settings.max_research_context_chars = 1
    sources = [ready_source()[0].id for _ in range(2)]
    run = create_run(db, "Compare", sources, settings)
    assert retrieval.retrieve_evidence(db, run, settings, perf_counter()) == []
    assert {row.status for row in db.scalars(select(SourceCoverage))} == {"context_limited"}


def test_no_chunks_and_missing_snapshot_are_distinct(db, settings, ready_source, azure_api):
    first, _, _ = ready_source(())
    second, document, _ = ready_source()
    run = create_run(db, "Compare", [first.id, second.id], settings)
    document.status = "failed"
    db.commit()
    with pytest.raises(NexusError) as error:
        retrieval.retrieve_evidence(db, run, settings, perf_counter())
    assert error.value.code == "SOURCE_VERSION_UNAVAILABLE"
    assert {row.status for row in db.scalars(select(SourceCoverage))} == {
        "no_relevant_evidence",
        "parse_unavailable",
    }


def test_source_database_failure_is_recorded(db, settings, ready_source, azure_api, monkeypatch):
    sources = [ready_source()[0].id for _ in range(2)]
    run = create_run(db, "Compare", sources, settings)

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private database details")

    monkeypatch.setattr(retrieval, "search_chunks", fail)
    with pytest.raises(NexusError) as error:
        retrieval.retrieve_evidence(db, run, settings, perf_counter())
    assert error.value.code == "RETRIEVAL_FAILED"
    assert "private" not in str(error.value)
    assert "retrieval_failed" in {row.status for row in db.scalars(select(SourceCoverage))}
    assert db.scalar(select(EvidenceItem)) is None
