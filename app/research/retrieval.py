from copy import deepcopy
from time import perf_counter

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document
from app.db.research_models import (
    EvidenceItem,
    ResearchRetrievalResult,
    ResearchRun,
    ResearchRunSource,
    SourceCoverage,
)
from app.embeddings.azure_openai import (
    AzureEmbeddingConfigurationError,
    AzureEmbeddingError,
    AzureEmbeddingTimeoutError,
    embed_text,
)
from app.errors import NexusError
from app.retrieval.citations import citation_display
from app.retrieval.vector_search import search_chunks


def retrieve_evidence(
    db: Session, run: ResearchRun, settings: Settings, started: float
) -> list[EvidenceItem]:
    """Embed once, search each pinned snapshot, and persist the exact model context."""
    if run.status != "created":
        raise NexusError("RESEARCH_RUN_IMMUTABLE", "Create a new run for a new execution.", 409)
    run.status = "retrieving"
    db.commit()
    remaining = run.answer_config["timeout_seconds"] - (perf_counter() - started)
    if remaining <= 0:
        raise NexusError("RESEARCH_TIMEOUT", "The research time limit was exceeded.", 504)
    provider_settings = settings.model_copy(
        update={"provider_timeout_seconds": min(settings.provider_timeout_seconds, remaining)}
    )
    try:
        embedding = embed_text(run.question, provider_settings)
    except AzureEmbeddingConfigurationError as exc:
        raise NexusError("EMBEDDING_NOT_CONFIGURED", str(exc), 503) from exc
    except AzureEmbeddingTimeoutError as exc:
        raise NexusError("RESEARCH_TIMEOUT", str(exc), 504, retryable=True) from exc
    except AzureEmbeddingError as exc:
        raise NexusError("EMBEDDING_FAILED", str(exc), 502, retryable=True) from exc
    run.embedding_tokens = embedding.prompt_tokens
    run.retrieval_config = {
        **run.retrieval_config,
        "embedding_model": embedding.model,
        "metric": "cosine_distance",
    }
    db.commit()

    sources = db.execute(
        select(ResearchRunSource, SourceCoverage)
        .join(SourceCoverage, SourceCoverage.research_run_source_id == ResearchRunSource.id)
        .where(ResearchRunSource.research_run_id == run.id)
        .order_by(ResearchRunSource.source_order)
    ).all()
    # Fixed per-source shares keep a large document from consuming every context slot.
    source_chars = run.retrieval_config["max_context_chars"] // len(sources)
    source_items = run.retrieval_config["max_evidence"] // len(sources)
    evidence = []
    for pin, coverage in sources:
        source_started = perf_counter()
        remaining = run.answer_config["timeout_seconds"] - (source_started - started)
        if remaining <= 0:
            raise NexusError("RESEARCH_TIMEOUT", "The research time limit was exceeded.", 504)
        try:
            with db.begin_nested():
                db.execute(
                    text("SELECT set_config('statement_timeout', :value, true)"),
                    {"value": str(max(1, int(remaining * 1000)))},
                )
                document = db.get(Document, pin.document_id, populate_existing=True)
                if document is None or document.status != "ready":
                    coverage.status = "parse_unavailable"
                    coverage.detail = "The pinned document snapshot is unavailable."
                    db.flush()
                    chunks = None
                else:
                    chunks = search_chunks(
                        db,
                        embedding.vector,
                        [pin.source_id],
                        settings,
                        top_k=run.retrieval_config["top_k_per_source"],
                        document_id=pin.document_id,
                        embedding_model=embedding.model,
                    )
        except SQLAlchemyError as exc:
            coverage.status = "retrieval_failed"
            coverage.detail = "The pinned-source search could not be completed."
            coverage.duration_ms = round((perf_counter() - source_started) * 1000)
            db.commit()
            code = getattr(exc.orig, "sqlstate", None) if hasattr(exc, "orig") else None
            if code == "57014":
                raise NexusError("RESEARCH_TIMEOUT", "The source search timed out.", 504) from exc
            raise NexusError("RETRIEVAL_FAILED", coverage.detail, 503, retryable=True) from exc
        if chunks is None:
            db.commit()
            raise NexusError("SOURCE_VERSION_UNAVAILABLE", coverage.detail, 409)

        selected_chars = 0
        selected_count = 0
        for rank, chunk in enumerate(chunks, start=1):
            if chunk.document_id != pin.document_id or chunk.source_id != pin.source_id:
                raise NexusError(
                    "EVIDENCE_VALIDATION_FAILED", "Retrieved passage is out of scope.", 502
                )
            selected = (
                selected_chars + len(chunk.text) <= source_chars and selected_count < source_items
            )
            result = ResearchRetrievalResult(
                research_run_id=run.id,
                research_run_source_id=pin.id,
                chunk_id=chunk.chunk_id,
                source_rank=rank,
                score=chunk.cosine_distance,
                selected=selected,
            )
            db.add(result)
            db.flush()
            if selected:
                item = EvidenceItem(
                    research_run_id=run.id,
                    retrieval_result_id=result.id,
                    chunk_id=chunk.chunk_id,
                    label=f"E{len(evidence) + 1}",
                    excerpt=chunk.text,
                    locator_snapshot=deepcopy(chunk.locator),
                    source_display_name=pin.display_name,
                    display_text=citation_display(pin.display_name, chunk),
                )
                db.add(item)
                evidence.append(item)
                selected_count += 1
                selected_chars += len(chunk.text)
        coverage.retrieved_chunk_count = len(chunks)
        coverage.selected_chunk_count = selected_count
        coverage.context_limited = selected_count < len(chunks)
        coverage.status = (
            "retrieved"
            if selected_count
            else "context_limited"
            if chunks
            else "no_relevant_evidence"
        )
        coverage.detail = (
            "Some retrieved passages exceeded this source's context or evidence allowance."
            if coverage.context_limited
            else "No indexed passages matched the configured embedding model."
            if not chunks
            else None
        )
        coverage.duration_ms = round((perf_counter() - source_started) * 1000)
        db.commit()

    run.retrieval_ms = round((perf_counter() - started) * 1000)
    run.retrieval_config = {
        **run.retrieval_config,
        "context_chars": sum(len(item.excerpt) for item in evidence),
        "selected_chunk_count": len(evidence),
        "context_chars_per_source": source_chars,
        "evidence_per_source": source_items,
    }
    db.commit()
    return evidence
