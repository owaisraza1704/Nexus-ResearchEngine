from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.embeddings.azure_openai import AzureEmbeddingConfigurationError, AzureEmbeddingError
from app.retrieval.vector_search import RetrievedChunk, retrieve_question

router = APIRouter(tags=["retrieval"])


class RetrievalRequest(BaseModel):
    question: str
    source_ids: list[UUID]
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
) -> RetrievalResponse | JSONResponse:
    try:
        chunks = retrieve_question(
            db,
            request.question,
            request.source_ids,
            settings,
            top_k=request.top_k,
        )
    except (AzureEmbeddingConfigurationError, AzureEmbeddingError) as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "RETRIEVAL_EMBEDDING_FAILED",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "INVALID_RETRIEVAL_REQUEST",
                    "message": str(exc),
                    "retryable": False,
                }
            },
        )

    return RetrievalResponse(chunks=[_chunk_response(chunk) for chunk in chunks])
