from copy import deepcopy
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
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
from app.errors import NexusError
from app.research.synthesis import GeneratedGap, GeneratedResearch, validate_output


def evidence_rows(db: Session, run_id):
    """Load and check the saved evidence chain used by both persistence and API reads."""
    rows = db.execute(
        select(EvidenceItem, ResearchRetrievalResult, ResearchRunSource, DocumentChunk, Document)
        .join(
            ResearchRetrievalResult, EvidenceItem.retrieval_result_id == ResearchRetrievalResult.id
        )
        .join(
            ResearchRunSource,
            ResearchRetrievalResult.research_run_source_id == ResearchRunSource.id,
        )
        .join(DocumentChunk, EvidenceItem.chunk_id == DocumentChunk.id)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(EvidenceItem.research_run_id == run_id)
        .order_by(ResearchRunSource.source_order, ResearchRetrievalResult.source_rank)
    ).all()
    for item, retrieval, pin, chunk, document in rows:
        if (
            retrieval.research_run_id != run_id
            or pin.research_run_id != run_id
            or chunk.document_id != pin.document_id
            or document.source_id != pin.source_id
            or not retrieval.selected
        ):
            raise NexusError(
                "EVIDENCE_VALIDATION_FAILED", "Saved evidence is outside the run scope.", 502
            )
    return rows


def save_result(
    db: Session,
    run: ResearchRun,
    generated: GeneratedResearch,
    started: float,
    *,
    commit: bool = True,
) -> ResearchResult:
    """Commit validated claims, coverage, citations, and the result as one transaction."""
    if run.status != "synthesizing":
        raise NexusError("RESEARCH_RUN_IMMUTABLE", "Only an active run can save a result.", 409)
    rows = evidence_rows(db, run.id)
    if any(
        item.excerpt != chunk.text or item.locator_snapshot != chunk.locator
        for item, _, _, chunk, _ in rows
    ):
        raise NexusError(
            "EVIDENCE_VALIDATION_FAILED", "Evidence does not match its source snapshot.", 502
        )
    evidence = [row[0] for row in rows]
    source_by_label = {item.label: pin.id for item, _, pin, _, _ in rows}
    validate_output(run, generated, evidence, source_by_label)
    by_label = {item.label: item for item in evidence}
    relevant = set(generated.relevant_evidence_ids)
    for item in evidence:
        item.used = item.label in relevant

    gaps = list(generated.gaps)
    sources = db.execute(
        select(ResearchRunSource, SourceCoverage)
        .join(SourceCoverage, SourceCoverage.research_run_source_id == ResearchRunSource.id)
        .where(ResearchRunSource.research_run_id == run.id)
        .order_by(ResearchRunSource.source_order)
    ).all()
    for pin, coverage in sources:
        coverage.evidence_count = sum(source_by_label[label] == pin.id for label in relevant)
        if coverage.evidence_count:
            coverage.status = "used"
        elif coverage.context_limited:
            coverage.status = "context_limited"
        else:
            coverage.status = "no_relevant_evidence"
            coverage.detail = (
                coverage.detail or "No relevant evidence was identified in the retrieved context."
            )
        if coverage.context_limited:
            gaps.append(
                GeneratedGap(
                    reason="scope_limit",
                    text=(
                        f"{pin.display_name}: some retrieved passages were excluded "
                        "by the context budget."
                    ),
                )
            )
        elif not coverage.evidence_count:
            gaps.append(
                GeneratedGap(
                    reason="no_evidence",
                    text=(
                        f"{pin.display_name}: no relevant evidence was identified "
                        "in the retrieved context."
                    ),
                )
            )

    for sequence, proposal in enumerate(generated.claims, start=1):
        claim = Claim(
            research_run_id=run.id,
            sequence=sequence,
            claim_text=proposal.text,
            claim_type=proposal.claim_type,
            support_status=proposal.support_status,
        )
        db.add(claim)
        db.flush()
        for link in proposal.evidence:
            db.add(
                ClaimEvidence(
                    research_run_id=run.id,
                    claim_id=claim.id,
                    evidence_item_id=by_label[link.evidence_id].id,
                    relationship=link.relationship,
                    explanation=link.explanation,
                )
            )
        if claim.support_status in {"unresolved", "partially_supported"}:
            gaps.append(
                GeneratedGap(
                    reason="no_evidence",
                    text=(f"Claim requires additional evidence: {claim.claim_text}"),
                )
            )
        elif claim.support_status == "contradicted":
            gaps.append(
                GeneratedGap(
                    reason="conflict",
                    text=(f"Candidate contradiction requires review: {claim.claim_text}"),
                )
            )

    seen_gaps = set()
    for gap in gaps:
        key = (gap.reason, gap.text)
        if key not in seen_gaps:
            seen_gaps.add(key)
            db.add(
                ResearchGap(
                    research_run_id=run.id,
                    sequence=len(seen_gaps),
                    gap_text=gap.text,
                    reason=gap.reason,
                )
            )
    result = ResearchResult(
        research_run_id=run.id,
        status=generated.status,
        summary=generated.limitation
        if generated.status == "insufficient_context"
        else generated.summary,
        limitation=generated.limitation,
        duration_ms=round((perf_counter() - started) * 1000),
    )
    db.add(result)
    db.flush()
    for item in evidence:
        if item.used:
            db.add(
                ResultCitation(
                    research_run_id=run.id,
                    research_result_id=result.id,
                    evidence_item_id=item.id,
                    label=item.label,
                    display_text=item.display_text,
                    locator_snapshot=deepcopy(item.locator_snapshot),
                )
            )
    run.status = generated.status
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = round((perf_counter() - started) * 1000)
    result.duration_ms = run.duration_ms
    if perf_counter() - started > run.answer_config["timeout_seconds"]:
        raise NexusError("RESEARCH_TIMEOUT", "The research time limit was exceeded.", 504)
    if commit:
        db.commit()
    else:
        db.flush()
    return result
