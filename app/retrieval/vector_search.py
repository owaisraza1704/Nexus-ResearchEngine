from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source
from app.embeddings.azure_openai import embed_text


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk ranked by vector similarity for one retrieval request."""

    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    sequence: int
    text: str
    locator: dict[str, Any]
    cosine_distance: float


def search_chunks(
    db: Session,
    query_vector: Sequence[float],
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
    document_id: UUID | None = None,
    embedding_model: str | None = None,
) -> tuple[RetrievedChunk, ...]:
    """Return the nearest ready chunks from the selected sources."""

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    selected_source_ids = tuple(source_ids)
    if not selected_source_ids:
        return ()

    vector = [float(value) for value in query_vector]
    expected_dimensions = settings.azure_openai_embedding_dimensions
    if len(vector) != expected_dimensions:
        raise ValueError(
            "query_vector has an unexpected dimension: "
            f"expected {expected_dimensions}, got {len(vector)}"
        )

    deployment = settings.azure_openai_embedding_deployment
    if not deployment:
        raise ValueError("azure_openai_embedding_deployment is required for retrieval")

    cosine_distance = ChunkEmbedding.embedding.cosine_distance(vector).label("cosine_distance")
    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id.label("document_id"),
            Source.id.label("source_id"),
            DocumentChunk.sequence,
            DocumentChunk.text,
            DocumentChunk.locator,
            cosine_distance,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(
            Source.id.in_(selected_source_ids),
            Document.status == "ready",
            ChunkEmbedding.provider == "azure_openai",
            ChunkEmbedding.deployment == deployment,
            ChunkEmbedding.dimensions == expected_dimensions,
        )
        .order_by(cosine_distance, DocumentChunk.sequence, DocumentChunk.id)
        .limit(top_k)
    )
    if document_id is None:
        statement = statement.where(
            Source.current_document_id == Document.id, Source.status == "ready"
        )
    else:
        statement = statement.where(Document.id == document_id)
    if embedding_model is not None:
        statement = statement.where(ChunkEmbedding.model == embedding_model)

    rows = db.execute(statement).all()
    return tuple(
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source_id=row.source_id,
            sequence=row.sequence,
            text=row.text,
            locator=row.locator,
            cosine_distance=float(row.cosine_distance),
        )
        for row in rows
    )


def retrieve_question(
    db: Session,
    question: str,
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
) -> tuple[RetrievedChunk, ...]:
    """Embed one question and return its nearest ready chunks."""

    query_embedding = embed_text(question, settings)
    return search_chunks(
        db,
        query_embedding.vector,
        source_ids,
        settings,
        top_k=top_k,
    )
