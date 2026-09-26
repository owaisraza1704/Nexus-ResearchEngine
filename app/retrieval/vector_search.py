from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source
from app.embeddings.azure_openai import embed_text


@dataclass(frozen=True)
class RetrievedChunk:
    """A ranked passage; fusion scores are not probabilities or cosine distances."""

    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    sequence: int
    text: str
    locator: dict[str, Any]
    cosine_distance: float
    fusion_score: float | None = None
    lexical_score: float | None = None


def search_chunks(
    db: Session,
    query_vector: Sequence[float],
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
    document_id: UUID | None = None,
    embedding_model: str | None = None,
    strategy: Literal["vector", "hybrid"] = "vector",
    question: str | None = None,
) -> tuple[RetrievedChunk, ...]:
    """Search the same pinned scope with vectors, optionally fused with keyword ranks."""

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    if strategy not in {"vector", "hybrid"}:
        raise ValueError("Unknown retrieval strategy")
    if strategy == "hybrid" and not question:
        raise ValueError("question is required for hybrid retrieval")

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
    )
    if document_id is None:
        statement = statement.where(
            Source.current_document_id == Document.id, Source.status == "ready"
        )
    else:
        statement = statement.where(Document.id == document_id)
    if embedding_model is not None:
        statement = statement.where(ChunkEmbedding.model == embedding_model)

    candidate_count = min(max(top_k * 4, 20), 100) if strategy == "hybrid" else top_k
    dense_rows = db.execute(
        statement.order_by(cosine_distance, DocumentChunk.sequence, DocumentChunk.id).limit(
            candidate_count
        )
    ).all()
    chunks = {
        str(row.chunk_id): RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source_id=row.source_id,
            sequence=row.sequence,
            text=row.text,
            locator=row.locator,
            cosine_distance=float(row.cosine_distance),
        )
        for row in dense_rows
    }
    if strategy == "vector" or not dense_rows:
        return tuple(chunks.values())

    # A question usually contains words absent from any single passage. PostgreSQL
    # tokenizes/stems it; OR the resulting terms so keywords complement dense recall.
    terms = cast(func.plainto_tsquery("english", question), Text)
    query = cast(func.replace(terms, " & ", " | "), TSQUERY)
    lexical_score = func.ts_rank_cd(DocumentChunk.search_vector, query).label("lexical_score")
    lexical_rows = db.execute(
        statement.add_columns(lexical_score)
        .where(DocumentChunk.search_vector.op("@@")(query))
        .order_by(lexical_score.desc(), DocumentChunk.sequence, DocumentChunk.id)
        .limit(candidate_count)
    ).all()
    for row in lexical_rows:
        chunks[str(row.chunk_id)] = RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source_id=row.source_id,
            sequence=row.sequence,
            text=row.text,
            locator=row.locator,
            cosine_distance=float(row.cosine_distance),
            lexical_score=float(row.lexical_score),
        )

    # ranx supplies RRF. Ordinal inputs preserve SQL's deterministic tie order.
    from ranx import Run
    from ranx.fusion import rrf

    runs = [
        Run(
            {"query": {str(row.chunk_id): float(len(rows) - rank) for rank, row in enumerate(rows)}}
        )
        for rows in (dense_rows, lexical_rows)
        if rows
    ]
    scores = rrf(runs, k=60).to_dict()["query"]
    ordered = sorted(scores, key=lambda key: (-scores[key], chunks[key].sequence, key))
    return tuple(replace(chunks[key], fusion_score=float(scores[key])) for key in ordered[:top_k])


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
