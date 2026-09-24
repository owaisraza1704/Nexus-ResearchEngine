import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document, Query, RetrievalResult, Source
from app.embeddings.azure_openai import (
    AzureEmbeddingConfigurationError,
    AzureEmbeddingError,
    AzureEmbeddingTimeoutError,
    embed_text,
)
from app.errors import NexusError
from app.retrieval.vector_search import RetrievedChunk, search_chunks

logger = logging.getLogger(__name__)


@dataclass
class RetrievalRun:
    query: Query
    chunks: tuple[RetrievedChunk, ...]
    results: list[RetrievalResult]


def fail_query(db: Session, query: Query, error: NexusError, started: float) -> None:
    """Keep provider/output failures traceable without saving a successful answer."""
    db.rollback()
    query.status = "failed"
    query.error_code = error.code
    query.duration_ms = round((perf_counter() - started) * 1000)
    query.completed_at = datetime.now(timezone.utc)
    db.commit()
    error.query_id = query.id
    logger.warning("query_failed query_id=%s code=%s", query.id, error.code)


def retrieve_and_save(
    db: Session,
    question: str,
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
) -> RetrievalRun:
    """Pin one ready document, then save the question and its ranked evidence."""
    question = question.strip()
    if not question or len(question) > settings.max_question_chars:
        raise NexusError(
            "INVALID_QUESTION",
            f"Question must contain 1 to {settings.max_question_chars} characters.",
        )
    if len(source_ids) != 1:
        raise NexusError("INVALID_SOURCE_SELECTION", "Select exactly one source for MVP-1.")
    if not 1 <= top_k <= settings.max_top_k:
        raise NexusError("INVALID_TOP_K", f"top_k must be between 1 and {settings.max_top_k}.")

    source = db.get(Source, source_ids[0])
    if source is None:
        raise NexusError("SOURCE_NOT_FOUND", "The requested source does not exist.", 404)
    document = db.get(Document, source.current_document_id) if source.current_document_id else None
    if (
        source.status != "ready"
        or document is None
        or document.status != "ready"
        or document.source_id != source.id
    ):
        raise NexusError("SOURCE_NOT_READY", "The source has no ready document to search.", 409)

    started = perf_counter()
    query = Query(
        question=question,
        source_ids=[str(source.id)],
        document_id=document.id,
        retrieval_config={
            "top_k": top_k,
            "embedding_provider": "azure_openai",
            "embedding_deployment": settings.azure_openai_embedding_deployment,
            "embedding_dimensions": settings.azure_openai_embedding_dimensions,
        },
        status="retrieving",
    )
    db.add(query)
    db.commit()

    try:
        embedding = embed_text(question, settings)
    except AzureEmbeddingConfigurationError as exc:
        error = NexusError("EMBEDDING_NOT_CONFIGURED", str(exc), 503)
        fail_query(db, query, error, started)
        raise error from exc
    except AzureEmbeddingTimeoutError as exc:
        error = NexusError("EMBEDDING_TIMEOUT", str(exc), 504, retryable=True)
        fail_query(db, query, error, started)
        raise error from exc
    except AzureEmbeddingError as exc:
        error = NexusError("EMBEDDING_FAILED", str(exc), 502, retryable=True)
        fail_query(db, query, error, started)
        raise error from exc

    chunks = search_chunks(
        db,
        embedding.vector,
        source_ids,
        settings,
        top_k=top_k,
        document_id=query.document_id,
        embedding_model=embedding.model,
    )
    results = [
        RetrievalResult(
            query_id=query.id,
            chunk_id=chunk.chunk_id,
            rank=rank,
            cosine_distance=chunk.cosine_distance,
            selected=False,
        )
        for rank, chunk in enumerate(chunks, start=1)
    ]
    db.add_all(results)
    query.duration_ms = round((perf_counter() - started) * 1000)
    query.retrieval_config = {
        **query.retrieval_config,
        "embedding_model": embedding.model,
        "embedding_tokens": embedding.prompt_tokens,
        "candidate_count": len(chunks),
        "duration_ms": query.duration_ms,
    }
    query.status = "retrieved"
    db.commit()
    logger.info("retrieval_saved query_id=%s chunks=%s", query.id, len(chunks))
    return RetrievalRun(query, chunks, results)
