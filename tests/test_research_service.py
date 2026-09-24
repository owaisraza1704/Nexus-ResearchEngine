import json
from copy import deepcopy
from time import perf_counter
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.research_models import (
    Claim,
    ClaimEvidence,
    EvidenceItem,
    ResearchGap,
    ResearchResult,
    ResearchRun,
    ResultCitation,
    SourceCoverage,
)
from app.errors import NexusError
from app.llm import azure_openai as llm
from app.research import results, retrieval, service
from app.research.synthesis import RESEARCH_INSTRUCTIONS, GeneratedResearch


def test_complete_research_persists_claims_citations_coverage_and_usage(
    db, settings, research_sources, research_azure
):
    ids = [source.id for source, _, _ in research_sources]
    result = service.research(db, "Compare retention", ids, settings)
    run = db.get(ResearchRun, result.research_run_id)
    assert result.status == run.status == "completed"
    assert db.scalar(select(func.count()).select_from(Claim)) == 2
    assert db.scalar(select(func.count()).select_from(ClaimEvidence)) == 2
    assert db.scalar(select(func.count()).select_from(ResultCitation)) == 2
    assert all(item.used for item in db.scalars(select(EvidenceItem)))
    assert {row.status for row in db.scalars(select(SourceCoverage))} == {"used"}
    assert run.embedding_tokens == 8
    assert (run.input_tokens, run.output_tokens) == (100, 20)
    assert run.llm_model == "test-chat-version"
    assert run.llm_deployment == settings.azure_openai_model
    assert run.completed_at is not None
    assert run.duration_ms == result.duration_ms
    assert len(research_azure["calls"]) == 2
    chat = research_azure["calls"][1][1]
    assert chat["max_completion_tokens"] == 6000
    assert chat["response_format"]["json_schema"]["strict"] is True
    assert chat["messages"][0]["content"] == RESEARCH_INSTRUCTIONS
    prompt = json.loads(chat["messages"][1]["content"])
    assert len(prompt["sources"]) == 2
    assert "score" not in prompt["sources"][0]
    assert prompt["sources"][0]["passages"][0]["text"] == research_sources[0][2][0].text
    with pytest.raises(NexusError, match="active run"):
        results.save_result(db, run, GeneratedResearch(**research_azure["answer"]), perf_counter())


def test_irrelevant_third_source_is_reported_not_silently_omitted(
    db, settings, research_sources, research_azure, ready_source
):
    third, _, _ = ready_source(("Cafeteria lunch is served at noon.",))
    ids = [source.id for source, _, _ in research_sources] + [third.id]
    result = service.research(db, "Compare retention", ids, settings)
    assert result.status == "completed"
    assert db.scalar(select(func.count()).select_from(SourceCoverage)) == 3
    statuses = [row.status for row in db.scalars(select(SourceCoverage))]
    assert statuses.count("used") == 2
    assert statuses.count("no_relevant_evidence") == 1
    assert len(db.scalars(select(EvidenceItem).where(EvidenceItem.used.is_(True))).all()) == 2
    assert db.scalar(select(ResearchGap.reason)) == "no_evidence"


def test_contradictions_qualifications_and_unresolved_claims_have_explicit_gaps(
    db, settings, research_sources, research_azure
):
    output = research_azure["answer"]
    output["claims"][0]["support_status"] = "contradicted"
    output["claims"][0]["evidence"].append(
        {
            "evidence_id": "E2",
            "relationship": "contradicts",
            "explanation": "Conflicting retention.",
        }
    )
    output["claims"][1]["support_status"] = "partially_supported"
    output["claims"][1]["evidence"].append(
        {"evidence_id": "E1", "relationship": "qualifies", "explanation": "Different conditions."}
    )
    output["claims"].append(
        {
            "text": "The retention policy after migration is unresolved.",
            "claim_type": "gap",
            "support_status": "unresolved",
            "evidence": [{"evidence_id": "E1", "relationship": "context", "explanation": None}],
        }
    )
    service.research(db, "Compare retention", [row[0].id for row in research_sources], settings)
    assert {row.relationship for row in db.scalars(select(ClaimEvidence))} == {
        "supports",
        "contradicts",
        "qualifies",
        "context",
    }
    gaps = db.scalars(select(ResearchGap).order_by(ResearchGap.sequence)).all()
    assert [gap.reason for gap in gaps] == ["conflict", "no_evidence", "no_evidence"]


@pytest.mark.parametrize("relevant", [[], ["E1"]])
def test_insufficient_context_retains_only_relevant_partial_evidence(
    db, settings, research_sources, research_azure, relevant
):
    research_azure["answer"] = {
        "status": "insufficient_context",
        "summary": "The requested information is unavailable.",
        "limitation": "The selected passages cannot support the full comparison.",
        "relevant_evidence_ids": relevant,
        "claims": [],
        "gaps": [{"reason": "no_evidence", "text": "Missing evidence for the comparison."}],
    }
    result = service.research(
        db, "Compare costs", [row[0].id for row in research_sources], settings
    )
    assert result.status == "insufficient_context"
    assert result.summary == result.limitation
    assert db.scalar(select(func.count()).select_from(Claim)) == 0
    assert db.scalar(select(func.count()).select_from(ResultCitation)) == len(relevant)
    assert sum(row.evidence_count for row in db.scalars(select(SourceCoverage))) == len(relevant)


@pytest.mark.parametrize("budget_limited", [False, True])
def test_empty_context_does_not_call_llm(
    db, settings, ready_source, research_azure, budget_limited
):
    if budget_limited:
        settings.max_research_context_chars = 1
    ids = [ready_source(("Large passage",) if budget_limited else ())[0].id for _ in range(2)]
    result = service.research(db, "Compare", ids, settings)
    assert result.status == "insufficient_context"
    assert len(research_azure["calls"]) == 1
    assert db.get(ResearchRun, result.research_run_id).input_tokens is None
    assert {row.status for row in db.scalars(select(SourceCoverage))} == {
        "context_limited" if budget_limited else "no_relevant_evidence"
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_evidence",
        "duplicate_evidence",
        "missing_support",
        "hidden_contradiction",
        "missing_contradiction",
        "same_support_and_contradiction",
        "unknown_summary_citation",
        "unknown_claim_citation",
        "unknown_gap_citation",
        "url",
        "too_many_claims",
        "one_source",
        "unused_relevant_source",
        "context_only_second_source",
        "unsupported_completed",
        "duplicate_link",
        "schema_invalid",
    ],
)
def test_invalid_output_fails_without_saving_partial_results(
    db, settings, research_sources, research_azure, mutation
):
    output = research_azure["answer"]
    claim = output["claims"][0]
    if mutation == "unknown_evidence":
        claim["evidence"][0]["evidence_id"] = "E99"
    elif mutation == "duplicate_evidence":
        output["relevant_evidence_ids"].append("E1")
    elif mutation == "missing_support":
        claim["evidence"] = []
    elif mutation == "hidden_contradiction":
        claim["evidence"].append(
            {"evidence_id": "E2", "relationship": "contradicts", "explanation": None}
        )
    elif mutation == "missing_contradiction":
        claim["support_status"] = "contradicted"
    elif mutation == "same_support_and_contradiction":
        claim["support_status"] = "contradicted"
        claim["evidence"].append(
            {"evidence_id": "E1", "relationship": "contradicts", "explanation": None}
        )
    elif mutation == "unknown_summary_citation":
        output["summary"] += " Made up [E99]."
    elif mutation == "unknown_claim_citation":
        claim["text"] += " [E99]"
    elif mutation == "unknown_gap_citation":
        output["gaps"] = [{"reason": "no_evidence", "text": "Unverified [E99]"}]
    elif mutation == "url":
        claim["text"] += " https://invented.example"
    elif mutation == "too_many_claims":
        output["claims"] = [deepcopy(claim) for _ in range(13)]
    elif mutation == "one_source":
        output["relevant_evidence_ids"] = ["E1"]
        output["claims"] = [claim]
        output["summary"] = "Only one source [E1]."
    elif mutation in {"unused_relevant_source", "context_only_second_source"}:
        output["claims"] = [claim]
        output["summary"] = "Only one source supports findings [E1]."
        if mutation == "context_only_second_source":
            claim["evidence"].append(
                {"evidence_id": "E2", "relationship": "context", "explanation": None}
            )
    elif mutation == "unsupported_completed":
        output["claims"] = []
    elif mutation == "duplicate_link":
        claim["evidence"].append(deepcopy(claim["evidence"][0]))
    elif mutation == "schema_invalid":
        output["invented_property"] = True
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "STRUCTURED_RESULT_INVALID"
    run = db.get(ResearchRun, error.value.run_id)
    assert run.status == "failed"
    assert run.completed_at is not None
    assert db.scalar(select(func.count()).select_from(ResearchResult)) == 0
    assert db.scalar(select(func.count()).select_from(Claim)) == 0
    assert db.scalar(select(func.count()).select_from(ResultCitation)) == 0


@pytest.mark.parametrize("stage", ["embedding", "chat"])
def test_provider_timeout_is_a_failed_run_not_insufficient_context(
    db, settings, research_sources, research_azure, stage
):
    research_azure[f"{stage}_error"] = httpx.ReadTimeout("private transport detail")
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "RESEARCH_TIMEOUT"
    assert "private" not in str(error.value)
    run = db.get(ResearchRun, error.value.run_id)
    assert run.status == "failed"
    assert {row.status for row in db.scalars(select(SourceCoverage))} == {"not_processed"}


def test_request_deadline_prevents_provider_execution(
    db, settings, research_sources, research_azure
):
    settings.research_timeout_seconds = 0.000001
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "RESEARCH_TIMEOUT"
    assert research_azure["calls"] == []


def test_deadline_after_generation_does_not_commit_a_success(
    db, settings, research_sources, research_azure, monkeypatch
):
    clock = {"elapsed": 0.0}
    now = perf_counter()
    for module in (service, retrieval, results):
        monkeypatch.setattr(module, "perf_counter", lambda: now + clock["elapsed"])
    generate = service.generate_structured

    def delayed(*args, **kwargs):
        output = generate(*args, **kwargs)
        clock["elapsed"] = settings.research_timeout_seconds + 1
        return output

    monkeypatch.setattr(service, "generate_structured", delayed)
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "RESEARCH_TIMEOUT"
    assert db.scalar(select(ResearchResult)) is None
    assert db.scalar(select(Claim)) is None


def test_result_write_failure_rolls_back_all_output(
    db, settings, research_sources, research_azure, monkeypatch
):
    commit = db.commit
    injected = {"done": False}

    def fail_once():
        if not injected["done"] and any(isinstance(row, ResultCitation) for row in db.new):
            injected["done"] = True
            raise SQLAlchemyError("private persistence detail")
        commit()

    monkeypatch.setattr(db, "commit", fail_once)
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "DATABASE_UNAVAILABLE"
    assert db.scalar(select(ResearchResult)) is None
    assert db.scalar(select(Claim)) is None
    assert db.scalar(select(ResultCitation)) is None
    assert db.get(ResearchRun, error.value.run_id).status == "failed"


def test_database_rejects_cross_run_claim_evidence(db, settings, research_sources, research_azure):
    ids = [row[0].id for row in research_sources]
    first = service.research(db, "Compare", ids, settings)
    second = service.research(db, "Compare again", ids, settings)
    claim = db.scalar(select(Claim).where(Claim.research_run_id == first.research_run_id))
    evidence = db.scalar(
        select(EvidenceItem).where(EvidenceItem.research_run_id == second.research_run_id)
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            ClaimEvidence(
                id=uuid4(),
                research_run_id=first.research_run_id,
                claim_id=claim.id,
                evidence_item_id=evidence.id,
                relationship="supports",
            )
        )
        db.flush()


@pytest.mark.parametrize(
    "stage,setting,code",
    [
        ("embedding", "azure_openai_embedding_deployment", "EMBEDDING_NOT_CONFIGURED"),
        ("chat", "azure_openai_model", "LLM_PROVIDER_NOT_CONFIGURED"),
    ],
)
def test_missing_provider_configuration_is_explicit(
    db, settings, research_sources, research_azure, stage, setting, code
):
    setattr(settings, setting, None)
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == code
    assert error.value.status_code == 503
    assert len(research_azure["calls"]) == (0 if stage == "embedding" else 1)


def test_rate_limit_is_not_retried_or_reported_as_insufficient_context(
    db, settings, research_sources, research_azure, mock_azure
):
    calls = []

    def limited(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "private provider detail"}})

    mock_azure(llm, limited)
    with pytest.raises(NexusError) as error:
        service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    assert error.value.code == "RESEARCH_GENERATION_FAILED"
    assert "private" not in str(error.value)
    assert len(calls) == 1
    assert db.scalar(select(ResearchResult)) is None


def test_insufficient_result_can_preserve_independently_supported_partial_claims(
    db, settings, research_sources, research_azure
):
    output = research_azure["answer"]
    output["status"] = "insufficient_context"
    output["summary"] = "There is no Gamma specification."
    output["limitation"] = "Alpha's retention is documented, but Gamma's retention is unknown."
    output["claims"] = output["claims"][:1]
    output["relevant_evidence_ids"] = ["E1"]
    output["gaps"] = [{"reason": "no_evidence", "text": "Gamma has no specification."}]
    result = service.research(
        db, "Compare Alpha with Gamma", [row[0].id for row in research_sources], settings
    )
    assert result.status == "insufficient_context"
    assert result.summary == output["limitation"]
    assert db.scalar(select(func.count()).select_from(Claim)) == 1
    assert db.scalar(select(Claim.support_status)) == "supported"
    assert db.scalar(select(func.count()).select_from(ResultCitation)) == 1


def test_conflict_must_be_structured_not_only_mentioned_in_gap_prose(
    db, settings, research_sources, research_azure
):
    research_azure["answer"]["gaps"] = [{"reason": "conflict", "text": "The policies disagree."}]
    with pytest.raises(NexusError, match="disputed claim"):
        service.research(db, "Compare policies", [row[0].id for row in research_sources], settings)
    assert db.scalar(select(ResearchResult)) is None


def test_saved_context_reconstructs_same_prompt_after_completion(
    db, settings, research_sources, research_azure
):
    result = service.research(db, "Compare", [row[0].id for row in research_sources], settings)
    original = research_azure["calls"][1][1]["messages"][1]["content"]
    assert service.build_prompt(db, db.get(ResearchRun, result.research_run_id)) == original


def test_supported_caveat_needs_support_links_not_just_qualifier_labels(
    db, settings, research_sources, research_azure
):
    claim = research_azure["answer"]["claims"][0]
    claim["text"] = "The duration is a retention policy, not a performance measurement."
    claim["evidence"][0]["relationship"] = "qualifies"
    with pytest.raises(NexusError, match="supporting evidence"):
        service.research(db, "Compare retention", [row[0].id for row in research_sources], settings)
    assert db.scalar(select(ResearchResult)) is None
