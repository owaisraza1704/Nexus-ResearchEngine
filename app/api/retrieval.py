from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.retrieval.service import retrieve_and_save
from app.retrieval.vector_search import RetrievedChunk

router = APIRouter(tags=["retrieval"])


class RetrievalRequest(BaseModel):
    question: str = Field(min_length=1)
    source_ids: list[UUID] = Field(min_length=1, max_length=1)
    top_k: int = Field(default=5, ge=1)


class RetrievalChunkResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    sequence: int
    text: str
    locator: dict[str, Any]
    cosine_distance: float


class RetrievalResponse(BaseModel):
    query_id: UUID
    document_id: UUID
    retrieval: dict
    chunks: list[RetrievalChunkResponse]


def _chunk_response(chunk: RetrievedChunk) -> RetrievalChunkResponse:
    return RetrievalChunkResponse(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_id=chunk.source_id,
        sequence=chunk.sequence,
        text=chunk.text,
        locator=chunk.locator,
        cosine_distance=chunk.cosine_distance,
    )


@router.post(
    "/v1/retrieval",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
)
def retrieve(
    request: RetrievalRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RetrievalResponse:
    run = retrieve_and_save(db, request.question, request.source_ids, settings, top_k=request.top_k)
    run.query.status = "completed"
    run.query.completed_at = datetime.now(timezone.utc)
    db.commit()
    return RetrievalResponse(
        query_id=run.query.id,
        document_id=run.query.document_id,
        retrieval=run.query.retrieval_config,
        chunks=[_chunk_response(chunk) for chunk in run.chunks],
    )
