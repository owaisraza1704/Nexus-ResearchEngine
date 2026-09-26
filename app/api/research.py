from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.research_models import (
    Claim,
    ClaimEvidence,
    EvidenceItem,
    ResearchGap,
    ResearchResult,
    ResearchRetrievalResult,
    ResearchRun,
    ResearchRunSource,
    ResultCitation,
    SourceCoverage,
)
from app.db.session import get_db
from app.errors import NexusError
from app.research.results import evidence_rows
from app.research.service import research

router = APIRouter(prefix="/v1/research/runs", tags=["research"])


class RetrievalOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top_k_per_source: int = Field(default=4, ge=1)


class OutputOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_claims: int | None = Field(default=None, ge=1)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1)
    source_ids: list[UUID]
    mode: Literal["comparison", "synthesis"] = "comparison"
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)
    output: OutputOptions = Field(default_factory=OutputOptions)


class ResearchUsage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    embedding_tokens: int | None
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int
    retrieval_ms: int
    synthesis_ms: int


class CoverageResponse(BaseModel):
    source_id: UUID
    document_id: UUID
    document_version: int
    display_name: str
    status: Literal[
        "pending",
        "retrieved",
        "used",
        "no_relevant_evidence",
        "parse_unavailable",
        "retrieval_failed",
        "context_limited",
        "not_processed",
    ]
    retrieved_chunk_count: int
    selected_chunk_count: int
    evidence_count: int
    context_limited: bool
    duration_ms: int
    detail: str | None


class EvidenceResponse(BaseModel):
    evidence_id: UUID
    label: str
    source_id: UUID
    document_id: UUID
    document_version: int
    chunk_id: UUID
    excerpt: str
    display_text: str
    locator: dict


class ClaimRelationshipResponse(BaseModel):
    evidence_id: UUID
    label: str
    relationship: Literal["supports", "contradicts", "qualifies", "context"]
    explanation: str | None


class ClaimResponse(BaseModel):
    claim_id: UUID
    text: str
    claim_type: Literal["comparison", "summary", "difference", "gap"]
    support_status: Literal["supported", "partially_supported", "contradicted", "unresolved"]
    evidence: list[str]
    relationships: list[ClaimRelationshipResponse]


class GapResponse(BaseModel):
    gap_id: UUID
    text: str
    reason: Literal["no_evidence", "source_unavailable", "conflict", "scope_limit"]


class ContradictionResponse(BaseModel):
    claim_id: UUID
    text: str
    status: Literal["candidate"] = "candidate"
    supporting_evidence: list[str]
    contradicting_evidence: list[str]


class CitationResponse(BaseModel):
    citation_id: UUID
    label: str
    evidence_id: UUID
    display_text: str
    locator: dict


class ResearchResponse(BaseModel):
    run_id: UUID
    result_id: UUID
    status: Literal["completed", "insufficient_context"]
    question: str
    mode: Literal["comparison", "synthesis"]
    summary: str
    limitation: str | None
    claims: list[ClaimResponse]
    evidence: list[EvidenceResponse]
    source_coverage: list[CoverageResponse]
    gaps: list[GapResponse]
    contradictions: list[ContradictionResponse]
    citations: list[CitationResponse]
    model: str | None
    prompt_version: str
    usage: ResearchUsage


class CandidateResponse(BaseModel):
    source_id: UUID
    document_id: UUID
    chunk_id: UUID
    source_rank: int
    cosine_distance: float
    ranking: dict = Field(default_factory=dict)
    selected: bool


class RunResponse(BaseModel):
    run_id: UUID
    question: str
    mode: Literal["comparison", "synthesis"]
    status: Literal[
        "created", "retrieving", "synthesizing", "completed", "insufficient_context", "failed"
    ]
    sources: list[CoverageResponse]
    retrieval: dict
    output: dict
    retrieval_results: list[CandidateResponse]
    embedding_provider: str
    llm_provider: str
    llm_deployment: str | None
    model: str | None
    prompt_version: str
    usage: ResearchUsage
    created_at: datetime
    completed_at: datetime | None
    error_code: str | None
    error_detail: str | None


def _coverage(db: Session, run_id: UUID) -> list[CoverageResponse]:
    rows = db.execute(
        select(ResearchRunSource, SourceCoverage)
        .join(SourceCoverage, SourceCoverage.research_run_source_id == ResearchRunSource.id)
        .where(ResearchRunSource.research_run_id == run_id)
        .order_by(ResearchRunSource.source_order)
    ).all()
    return [
        CoverageResponse(
            source_id=pin.source_id,
            document_id=pin.document_id,
            document_version=pin.document_version,
            display_name=pin.display_name,
            status=coverage.status,
            retrieved_chunk_count=coverage.retrieved_chunk_count,
            selected_chunk_count=coverage.selected_chunk_count,
            evidence_count=coverage.evidence_count,
            context_limited=coverage.context_limited,
            duration_ms=coverage.duration_ms,
            detail=coverage.detail,
        )
        for pin, coverage in rows
    ]


def _result_response(db: Session, result: ResearchResult) -> ResearchResponse:
    run = db.get(ResearchRun, result.research_run_id)
    rows = evidence_rows(db, run.id)
    used = {item.id: item for item, _, _, _, _ in rows if item.used}
    claims = db.scalars(
        select(Claim).where(Claim.research_run_id == run.id).order_by(Claim.sequence)
    ).all()
    links = db.execute(
        select(ClaimEvidence, EvidenceItem)
        .join(EvidenceItem, ClaimEvidence.evidence_item_id == EvidenceItem.id)
        .where(ClaimEvidence.research_run_id == run.id)
        .order_by(ClaimEvidence.claim_id, EvidenceItem.label, ClaimEvidence.relationship)
    ).all()
    citations = db.scalars(
        select(ResultCitation)
        .where(ResultCitation.research_result_id == result.id)
        .order_by(ResultCitation.label)
    ).all()
    if any(item.id not in used for _, item in links) or {
        citation.evidence_item_id for citation in citations
    } != set(used):
        raise NexusError(
            "EVIDENCE_VALIDATION_FAILED", "Saved result references invalid evidence.", 502
        )
    claim_responses = []
    contradictions = []
    for claim in claims:
        relationships = [
            ClaimRelationshipResponse(
                evidence_id=item.id,
                label=item.label,
                relationship=link.relationship,
                explanation=link.explanation,
            )
            for link, item in links
            if link.claim_id == claim.id
        ]
        claim_responses.append(
            ClaimResponse(
                claim_id=claim.id,
                text=claim.claim_text,
                claim_type=claim.claim_type,
                support_status=claim.support_status,
                evidence=list(dict.fromkeys(link.label for link in relationships)),
                relationships=relationships,
            )
        )
        if claim.support_status == "contradicted":
            contradictions.append(
                ContradictionResponse(
                    claim_id=claim.id,
                    text=claim.claim_text,
                    supporting_evidence=[
                        link.label for link in relationships if link.relationship == "supports"
                    ],
                    contradicting_evidence=[
                        link.label for link in relationships if link.relationship == "contradicts"
                    ],
                )
            )
    gaps = db.scalars(
        select(ResearchGap)
        .where(ResearchGap.research_run_id == run.id)
        .order_by(ResearchGap.sequence)
    ).all()
    return ResearchResponse(
        run_id=run.id,
        result_id=result.id,
        status=result.status,
        question=run.question,
        mode=run.mode,
        summary=result.summary,
        limitation=result.limitation,
        claims=claim_responses,
        evidence=[
            EvidenceResponse(
                evidence_id=item.id,
                label=item.label,
                source_id=pin.source_id,
                document_id=pin.document_id,
                document_version=pin.document_version,
                chunk_id=item.chunk_id,
                excerpt=item.excerpt,
                display_text=item.display_text,
                locator=item.locator_snapshot,
            )
            for item, _, pin, _, _ in rows
            if item.used
        ],
        source_coverage=_coverage(db, run.id),
        gaps=[GapResponse(gap_id=gap.id, text=gap.gap_text, reason=gap.reason) for gap in gaps],
        contradictions=contradictions,
        citations=[
            CitationResponse(
                citation_id=citation.id,
                label=citation.label,
                evidence_id=citation.evidence_item_id,
                display_text=citation.display_text,
                locator=citation.locator_snapshot,
            )
            for citation in citations
        ],
        model=run.llm_model,
        prompt_version=run.prompt_version,
        usage=ResearchUsage.model_validate(run),
    )


@router.post("", response_model=ResearchResponse)
def create_research_run(
    request: ResearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ResearchResponse:
    result = research(
        db,
        request.question,
        request.source_ids,
        settings,
        mode=request.mode,
        top_k_per_source=request.retrieval.top_k_per_source,
        max_claims=request.output.max_claims,
    )
    return _result_response(db, result)


@router.get("/{run_id}", response_model=RunResponse)
def get_research_run(run_id: UUID, db: Session = Depends(get_db)) -> RunResponse:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise NexusError("RESEARCH_RUN_NOT_FOUND", "The research run does not exist.", 404)
    rows = db.execute(
        select(ResearchRetrievalResult, ResearchRunSource)
        .join(
            ResearchRunSource,
            ResearchRetrievalResult.research_run_source_id == ResearchRunSource.id,
        )
        .where(ResearchRetrievalResult.research_run_id == run.id)
        .order_by(ResearchRunSource.source_order, ResearchRetrievalResult.source_rank)
    ).all()
    return RunResponse(
        run_id=run.id,
        question=run.question,
        mode=run.mode,
        status=run.status,
        sources=_coverage(db, run.id),
        retrieval=run.retrieval_config,
        output=run.answer_config,
        retrieval_results=[
            CandidateResponse(
                source_id=pin.source_id,
                document_id=pin.document_id,
                chunk_id=result.chunk_id,
                source_rank=result.source_rank,
                cosine_distance=result.score,
                ranking=result.ranking,
                selected=result.selected,
            )
            for result, pin in rows
        ],
        embedding_provider=run.embedding_provider,
        llm_provider=run.llm_provider,
        llm_deployment=run.llm_deployment,
        model=run.llm_model,
        prompt_version=run.prompt_version,
        usage=ResearchUsage.model_validate(run),
        created_at=run.created_at,
        completed_at=run.completed_at,
        error_code=run.error_code,
        error_detail=run.error_detail,
    )


@router.get("/{run_id}/result", response_model=ResearchResponse)
def get_research_result(run_id: UUID, db: Session = Depends(get_db)) -> ResearchResponse:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise NexusError("RESEARCH_RUN_NOT_FOUND", "The research run does not exist.", 404)
    if run.status == "failed":
        raise NexusError(
            "RESEARCH_RUN_FAILED",
            "This run failed; inspect its status for details.",
            409,
            run_id=run.id,
        )
    result = db.scalar(select(ResearchResult).where(ResearchResult.research_run_id == run.id))
    if result is None:
        raise NexusError(
            "RESEARCH_RESULT_NOT_READY", "This run has no completed result.", 409, run_id=run.id
        )
    return _result_response(db, result)
