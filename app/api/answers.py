from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.answers.service import answer_question
from app.config import Settings, get_settings
from app.db.models import Answer, AnswerCitation, DocumentChunk, Query, RetrievalResult
from app.db.session import get_db
from app.errors import NexusError

router = APIRouter(prefix="/v1/answers", tags=["answers"])


class RetrievalOptions(BaseModel):
    top_k: int = Field(default=5, ge=1)


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    source_ids: list[UUID] = Field(min_length=1, max_length=1)
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)


class CitationResponse(BaseModel):
    citation_id: UUID
    label: str
    retrieval_result_id: UUID
    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    display_text: str
    locator: dict


class AnswerUsage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int


class AnswerResponse(BaseModel):
    answer_id: UUID
    query_id: UUID
    status: Literal["completed", "insufficient_context"]
    answer: str
    limitation: str | None
    citations: list[CitationResponse]
    retrieval: dict
    model: str | None
    prompt_version: str
    usage: AnswerUsage


def _answer_response(db: Session, answer: Answer) -> AnswerResponse:
    query = db.get(Query, answer.query_id)
    rows = db.execute(
        select(AnswerCitation, RetrievalResult, DocumentChunk)
        .join(RetrievalResult, AnswerCitation.retrieval_result_id == RetrievalResult.id)
        .join(DocumentChunk, RetrievalResult.chunk_id == DocumentChunk.id)
        .where(AnswerCitation.answer_id == answer.id)
        .order_by(RetrievalResult.rank)
    ).all()
    return AnswerResponse(
        answer_id=answer.id,
        query_id=query.id,
        status=answer.status,
        answer=answer.answer_text,
        limitation=answer.limitation,
        citations=[
            CitationResponse(
                citation_id=citation.id,
                label=citation.label,
                retrieval_result_id=result.id,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                source_id=UUID(query.source_ids[0]),
                display_text=citation.display_text,
                locator=citation.locator_snapshot,
            )
            for citation, result, chunk in rows
        ],
        retrieval=query.retrieval_config,
        model=answer.llm_model,
        prompt_version=answer.prompt_version,
        usage=AnswerUsage(
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            duration_ms=answer.duration_ms,
        ),
    )


@router.post("", response_model=AnswerResponse)
def create_answer(
    request: AnswerRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnswerResponse:
    answer = answer_question(
        db, request.question, request.source_ids, settings, top_k=request.retrieval.top_k
    )
    return _answer_response(db, answer)


@router.get("/{answer_id}", response_model=AnswerResponse)
def get_answer(answer_id: UUID, db: Session = Depends(get_db)) -> AnswerResponse:
    answer = db.get(Answer, answer_id)
    if answer is None:
        raise NexusError("ANSWER_NOT_FOUND", "The requested answer does not exist.", 404)
    return _answer_response(db, answer)
