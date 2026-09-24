import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document, Source
from app.db.research_models import ResearchResult, ResearchRun, ResearchRunSource, SourceCoverage
from app.errors import NexusError
from app.llm.azure_openai import (
    AzureLLMConfigurationError,
    AzureLLMError,
    AzureLLMOutputError,
    AzureLLMTimeoutError,
    generate_structured,
)
from app.research.results import save_result
from app.research.retrieval import retrieve_evidence
from app.research.synthesis import (
    RESEARCH_INSTRUCTIONS,
    GeneratedGap,
    GeneratedResearch,
    build_prompt,
)

RESEARCH_PROMPT_VERSION = "research-v3"
logger = logging.getLogger(__name__)


def create_run(
    db: Session,
    question: str,
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    mode: str = "comparison",
    top_k_per_source: int = 4,
    max_claims: int | None = None,
    minimum_sources: int = 2,
    commit: bool = True,
) -> ResearchRun:
    """Validate the entire source set before saving its immutable snapshot selection."""
    question = question.strip()
    if not question or len(question) > settings.max_question_chars:
        raise NexusError("INVALID_QUESTION", "The research question is empty or too long.")
    if len(source_ids) < minimum_sources:
        raise NexusError("SOURCE_SET_TOO_SMALL", f"Select at least {minimum_sources} sources.")
    if len(source_ids) > settings.max_research_sources:
        raise NexusError("SOURCE_SET_TOO_LARGE", "Too many sources for one research run.")
    if len(set(source_ids)) != len(source_ids):
        raise NexusError("INVALID_SOURCE_SELECTION", "Select distinct sources.")
    if mode not in {"comparison", "synthesis"}:
        raise NexusError("INVALID_REQUEST", "Mode must be comparison or synthesis.")
    max_claims = settings.max_research_claims if max_claims is None else max_claims
    if not 1 <= top_k_per_source <= settings.max_top_k:
        raise NexusError("RESEARCH_LIMIT_EXCEEDED", "top_k_per_source exceeds the allowed range.")
    if not 1 <= max_claims <= settings.max_research_claims:
        raise NexusError("RESEARCH_LIMIT_EXCEEDED", "max_claims exceeds the allowed range.")

    snapshots = []
    for source_id in source_ids:
        source = db.get(Source, source_id)
        if source is None:
            raise NexusError("SOURCE_NOT_FOUND", "A selected source does not exist.", 404)
        document = (
            db.get(Document, source.current_document_id) if source.current_document_id else None
        )
        if (
            source.status != "ready"
            or document is None
            or document.status != "ready"
            or document.source_id != source.id
        ):
            raise NexusError(
                "SOURCE_NOT_READY", "Every selected source must have a ready snapshot.", 409
            )
        snapshots.append((source, document))

    run = ResearchRun(
        question=question,
        mode=mode,
        status="created",
        embedding_provider="azure_openai",
        llm_provider="azure_openai",
        llm_deployment=settings.azure_openai_model,
        prompt_version=RESEARCH_PROMPT_VERSION,
        retrieval_config={
            "top_k_per_source": top_k_per_source,
            "max_sources": settings.max_research_sources,
            "max_context_chars": settings.max_research_context_chars,
            "max_evidence": settings.max_research_evidence,
            "embedding_deployment": settings.azure_openai_embedding_deployment,
            "embedding_dimensions": settings.azure_openai_embedding_dimensions,
        },
        answer_config={
            "max_claims": max_claims,
            "max_output_chars": settings.max_research_output_chars,
            "max_output_tokens": settings.max_research_output_tokens,
            "timeout_seconds": settings.research_timeout_seconds,
            "provider_timeout_seconds": settings.provider_timeout_seconds,
        },
    )
    db.add(run)
    db.flush()
    for order, (source, document) in enumerate(snapshots, start=1):
        pin = ResearchRunSource(
            research_run_id=run.id,
            source_id=source.id,
            document_id=document.id,
            document_version=document.version,
            source_order=order,
            display_name=source.display_name,
        )
        db.add(pin)
        db.flush()
        db.add(SourceCoverage(research_run_id=run.id, research_run_source_id=pin.id))
    if commit:
        db.commit()
    else:
        db.flush()
    return run


def fail_run(db: Session, run: ResearchRun, error: NexusError, started: float) -> None:
    """Retain the failed execution and coverage, never a partly saved successful result."""
    db.rollback()
    run.status = "failed"
    run.error_code = error.code
    run.error_detail = str(error)
    run.duration_ms = round((perf_counter() - started) * 1000)
    run.completed_at = datetime.now(timezone.utc)
    for coverage in db.scalars(
        select(SourceCoverage).where(SourceCoverage.research_run_id == run.id)
    ):
        if coverage.status in {"pending", "retrieved"}:
            coverage.detail = (
                "Retrieval finished, but evidence assessment did not complete."
                if coverage.status == "retrieved"
                else "This source was not processed before the run failed."
            )
            coverage.status = "not_processed"
    db.commit()
    error.run_id = run.id
    logger.warning("research_failed run_id=%s code=%s", run.id, error.code)


def research(
    db: Session,
    question: str,
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    mode: str = "comparison",
    top_k_per_source: int = 4,
    max_claims: int | None = None,
) -> ResearchResult:
    """Execute one bounded, synchronous multi-document research request."""
    started = perf_counter()
    run = create_run(
        db,
        question,
        source_ids,
        settings,
        mode=mode,
        top_k_per_source=top_k_per_source,
        max_claims=max_claims,
    )
    try:
        evidence = retrieve_evidence(db, run, settings, started)
        run.status = "synthesizing"
        db.commit()
        synthesis_started = perf_counter()
        if not evidence:
            limited = (
                db.scalar(
                    select(SourceCoverage.id).where(
                        SourceCoverage.research_run_id == run.id,
                        SourceCoverage.context_limited.is_(True),
                    )
                )
                is not None
            )
            limitation = (
                "No retrieved passages fit the configured context allowance."
                if limited
                else "No indexed passages were available for the selected snapshots and model."
            )
            generated = GeneratedResearch(
                status="insufficient_context",
                summary=limitation,
                limitation=limitation,
                relevant_evidence_ids=[],
                claims=[],
                gaps=[
                    GeneratedGap(
                        text=limitation, reason="scope_limit" if limited else "no_evidence"
                    )
                ],
            )
        else:
            remaining = run.answer_config["timeout_seconds"] - (perf_counter() - started)
            if remaining <= 0:
                raise NexusError("RESEARCH_TIMEOUT", "The research time limit was exceeded.", 504)
            generation = generate_structured(
                build_prompt(db, run),
                GeneratedResearch,
                settings.model_copy(
                    update={"max_answer_tokens": run.answer_config["max_output_tokens"]}
                ),
                instructions=RESEARCH_INSTRUCTIONS,
                timeout_seconds=min(settings.provider_timeout_seconds, remaining),
            )
            generated = generation.parsed
            run.llm_model = generation.model
            run.input_tokens = generation.prompt_tokens
            run.output_tokens = generation.completion_tokens
        run.synthesis_ms = round((perf_counter() - synthesis_started) * 1000)
        db.commit()
        result = save_result(db, run, generated, started)
    except AzureLLMConfigurationError as exc:
        error = NexusError("LLM_PROVIDER_NOT_CONFIGURED", str(exc), 503)
        fail_run(db, run, error, started)
        raise error from exc
    except AzureLLMTimeoutError as exc:
        error = NexusError("RESEARCH_TIMEOUT", str(exc), 504, retryable=True)
        fail_run(db, run, error, started)
        raise error from exc
    except AzureLLMOutputError as exc:
        error = NexusError("STRUCTURED_RESULT_INVALID", str(exc), 502)
        fail_run(db, run, error, started)
        raise error from exc
    except AzureLLMError as exc:
        error = NexusError("RESEARCH_GENERATION_FAILED", str(exc), 502, retryable=True)
        fail_run(db, run, error, started)
        raise error from exc
    except NexusError as error:
        fail_run(db, run, error, started)
        raise
    except SQLAlchemyError as exc:
        error = NexusError(
            "DATABASE_UNAVAILABLE",
            "Research persistence could not be completed.",
            503,
            retryable=True,
            run_id=run.id,
        )
        # A full database outage may also prevent recording the terminal state.
        try:
            fail_run(db, run, error, started)
        except SQLAlchemyError:
            db.rollback()
            logger.error("research_failure_not_saved run_id=%s", error.run_id)
        raise error from exc
    logger.info(
        "research_saved run_id=%s status=%s duration_ms=%s", run.id, run.status, run.duration_ms
    )
    return result
