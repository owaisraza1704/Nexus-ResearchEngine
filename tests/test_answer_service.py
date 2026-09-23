from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.answers import service
from app.config import Settings
from app.retrieval.vector_search import RetrievedChunk


def _chunk(text: str, sequence: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source_id=uuid4(),
        sequence=sequence,
        text=text,
        locator={"page": sequence + 1},
        cosine_distance=0.2,
    )


def test_answer_question_retrieves_and_generates_from_labeled_context(monkeypatch) -> None:
    database = object()
    settings = Settings()
    source_id = uuid4()
    chunks = (_chunk("The platform creates a task graph.", 2), _chunk("It stores evidence.", 7))
    calls = {}

    def fake_retrieve_question(
        value_db,
        question,
        source_ids,
        value_settings,
        *,
        top_k,
    ):
        calls["retrieval"] = (value_db, question, source_ids, value_settings, top_k)
        return chunks

    def fake_generate_text(prompt, value_settings, *, instructions):
        calls["generation"] = (prompt, value_settings, instructions)
        return SimpleNamespace(
            text="The platform creates a task graph.",
            model="gpt-5.6-luna",
            prompt_tokens=30,
            completion_tokens=8,
        )

    monkeypatch.setattr(service, "retrieve_question", fake_retrieve_question)
    monkeypatch.setattr(service, "generate_text", fake_generate_text)

    result = service.answer_question(
        database,
        "What does the platform create?",
        [source_id],
        settings,
        top_k=2,
    )

    prompt, generation_settings, instructions = calls["generation"]
    assert result.text == "The platform creates a task graph."
    assert result.retrieved_chunks == chunks
    assert result.model == "gpt-5.6-luna"
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 8
    assert calls["retrieval"] == (
        database,
        "What does the platform create?",
        [source_id],
        settings,
        2,
    )
    assert "Question:\nWhat does the platform create?" in prompt
    assert f"[C1]\nchunk_id: {chunks[0].chunk_id}" in prompt
    assert chunks[0].text in prompt
    assert f"[C2]\nchunk_id: {chunks[1].chunk_id}" in prompt
    assert chunks[1].text in prompt
    assert instructions == service.GROUNDING_INSTRUCTIONS
    assert generation_settings is settings


def test_answer_question_does_not_generate_without_retrieved_context(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(service, "retrieve_question", lambda *args, **kwargs: ())
    monkeypatch.setattr(service, "generate_text", lambda *args, **kwargs: calls.append(True))

    with pytest.raises(service.InsufficientContextError, match="No relevant context"):
        service.answer_question(object(), "Question", [], Settings())

    assert calls == []
