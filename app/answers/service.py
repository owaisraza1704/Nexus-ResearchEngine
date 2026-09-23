from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.azure_openai import generate_text
from app.retrieval.vector_search import RetrievedChunk, retrieve_question

GROUNDED_ANSWER_PROMPT_VERSION = "grounded-answer-v1"
GROUNDING_INSTRUCTIONS = (
    "Answer using only the supplied source context. "
    "Do not use outside knowledge or invent unsupported details. "
    "If the context does not contain enough information, say that the context is insufficient."
)


class InsufficientContextError(RuntimeError):
    """Raised when retrieval returns no context for an answer."""


@dataclass(frozen=True)
class GroundedAnswer:
    """Generated answer together with the exact chunks supplied to the model."""

    text: str
    retrieved_chunks: tuple[RetrievedChunk, ...]
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


def answer_question(
    db: Session,
    question: str,
    source_ids: Sequence[UUID],
    settings: Settings,
    *,
    top_k: int = 5,
) -> GroundedAnswer:
    """Retrieve context and generate one answer from that context."""

    if not question.strip():
        raise ValueError("question must not be empty")

    retrieved_chunks = retrieve_question(
        db,
        question,
        source_ids,
        settings,
        top_k=top_k,
    )
    if not retrieved_chunks:
        raise InsufficientContextError("No relevant context was retrieved")

    generation = generate_text(
        _build_prompt(question, retrieved_chunks),
        settings,
        instructions=GROUNDING_INSTRUCTIONS,
    )
    return GroundedAnswer(
        text=generation.text,
        retrieved_chunks=retrieved_chunks,
        model=generation.model,
        prompt_tokens=generation.prompt_tokens,
        completion_tokens=generation.completion_tokens,
    )


def _build_prompt(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    labeled_chunks = []
    for index, chunk in enumerate(chunks, start=1):
        labeled_chunks.append(
            f"[C{index}]\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"sequence: {chunk.sequence}\n"
            f"{chunk.text}"
        )

    return (
        f"Prompt version: {GROUNDED_ANSWER_PROMPT_VERSION}\n\n"
        f"Question:\n{question.strip()}\n\n"
        "Source context:\n"
        + "\n\n".join(labeled_chunks)
    )
