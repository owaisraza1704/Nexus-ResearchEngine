import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.db.models import Answer, AnswerCitation, ChunkEmbedding, Document, Query, RetrievalResult
from app.retrieval.vector_search import search_chunks


def test_answer_persists_citations_and_can_be_reloaded(client, db, ready_source, azure_api):
    source, document, chunks = ready_source()
    response = client.post(
        "/v1/answers",
        json={
            "question": "What does Nexus produce?",
            "source_ids": [str(source.id)],
            "retrieval": {"top_k": 2},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["answer"].endswith("[C1]")
    assert body["model"] == "test-chat-version"
    assert body["usage"]["input_tokens"] == 100
    assert body["usage"]["output_tokens"] == 20
    citation = body["citations"][0]
    assert citation["chunk_id"] == str(chunks[0].id)
    assert citation["source_id"] == str(source.id)
    assert citation["document_id"] == str(document.id)
    assert citation["locator"] == chunks[0].locator
    assert "page(s) 1" in citation["display_text"]
    query = db.get(Query, UUID(body["query_id"]))
    assert query.status == "completed"
    assert query.document_id == document.id
    assert query.retrieval_config["selected_chunk_count"] == 2
    results = db.scalars(select(RetrievalResult).order_by(RetrievalResult.rank)).all()
    assert [result.context_label for result in results] == ["C1", "C2"]
    assert all(result.selected for result in results)
    prompt = json.loads(azure_api["calls"][1][1]["messages"][1]["content"])
    assert [part["text"] for part in prompt["source_context"]] == [chunk.text for chunk in chunks]
    db.expunge_all()
    assert client.get(f"/v1/answers/{body['answer_id']}").json() == body


def test_citation_snapshot_survives_current_document_change(
    client,
    db,
    settings,
    ready_source,
    azure_api,
):
    source, document, chunks = ready_source()
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    old_locator = body["citations"][0]["locator"]
    replacement = Document(
        source_id=source.id,
        version=2,
        status="ready",
        mime_type="application/pdf",
        parser_name="docling",
        parser_version="test",
        normalized_text="Replacement",
        document_metadata={},
    )
    db.add(replacement)
    db.flush()
    source.current_document_id = replacement.id
    source.display_name = "Renamed source"
    # Deliberately alter live metadata to verify the citation contains a copy.
    chunks[0].locator = {"changed": True}
    db.commit()
    saved = client.get(f"/v1/answers/{body['answer_id']}").json()
    assert saved["citations"][0]["locator"] == old_locator
    assert saved["citations"][0]["display_text"].startswith("Research fixture")
    assert saved["citations"][0]["document_id"] == str(document.id)
    assert (
        client.get(f"/v1/sources/{source.id}/chunks?document_id={document.id}").json()["total"] == 2
    )
    pinned = search_chunks(
        db,
        [1.0] + [0.0] * 3071,
        [source.id],
        settings,
        document_id=document.id,
        embedding_model="text-embedding-3-large",
    )
    assert len(pinned) == 2
    assert all(chunk.document_id == document.id for chunk in pinned)
    assert search_chunks(db, [1.0] + [0.0] * 3071, [source.id], settings) == ()


def test_model_can_explicitly_report_insufficient_context(client, db, ready_source, azure_api):
    source, _, _ = ready_source()
    azure_api["answer"] = {
        "status": "insufficient_context",
        "answer": "Unsupported draft must not be exposed.",
        "citation_ids": [],
        "limitation": "The document does not give a launch date.",
    }
    response = client.post(
        "/v1/answers",
        json={
            "question": "When was it launched?",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "insufficient_context"
    assert body["answer"] == body["limitation"] == azure_api["answer"]["limitation"]
    assert body["citations"] == []
    assert db.scalar(select(Query)).status == "insufficient_context"
    assert db.scalar(select(func.count()).select_from(AnswerCitation)) == 0


def test_empty_retrieval_saves_insufficient_answer_without_llm(client, db, ready_source, azure_api):
    source, _, _ = ready_source()
    db.execute(delete(ChunkEmbedding))
    db.commit()
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "insufficient_context"
    assert body["citations"] == []
    assert body["model"] is None
    assert body["usage"]["input_tokens"] is None
    assert len(azure_api["calls"]) == 1


def test_context_limit_selects_whole_passages(client, db, settings, ready_source, azure_api):
    source, _, chunks = ready_source()
    settings.max_context_chars = len(chunks[0].text)
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 200, response.text
    results = db.scalars(select(RetrievalResult).order_by(RetrievalResult.rank)).all()
    assert [result.selected for result in results] == [True, False]
    prompt = json.loads(azure_api["calls"][1][1]["messages"][1]["content"])
    assert prompt["source_context"] == [{"label": "C1", "text": chunks[0].text}]


def test_no_passage_fitting_context_limit_does_not_call_llm(
    client,
    settings,
    ready_source,
    azure_api,
):
    source, _, _ = ready_source()
    settings.max_context_chars = 1
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.json()["status"] == "insufficient_context"
    assert response.json()["retrieval"]["selected_chunk_count"] == 0
    assert len(azure_api["calls"]) == 1


@pytest.mark.parametrize(
    "output",
    [
        {
            "status": "completed",
            "answer": "Claim [C99]",
            "citation_ids": ["C99"],
            "limitation": None,
        },
        {
            "status": "completed",
            "answer": "Claim [C99]",
            "citation_ids": ["C1"],
            "limitation": None,
        },
        {"answer": "The structured fields are missing"},
    ],
)
def test_invalid_output_saves_failed_query_without_answer(
    client,
    db,
    ready_source,
    azure_api,
    output,
):
    source, _, _ = ready_source()
    azure_api["answer"] = output
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "INVALID_ANSWER_OUTPUT"
    query = db.get(Query, UUID(response.json()["error"]["query_id"]))
    assert query.status == "failed"
    assert query.completed_at is not None
    assert db.scalar(select(func.count()).select_from(Answer)) == 0
    assert db.scalar(select(func.count()).select_from(AnswerCitation)) == 0
    assert db.scalar(select(func.count()).select_from(RetrievalResult)) == 2


def test_answer_timeout_is_explicit_and_not_retried(client, db, ready_source, azure_api):
    source, _, _ = ready_source()
    azure_api["chat_error"] = httpx.ReadTimeout("secret provider information")
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 504, response.text
    assert response.json()["error"]["code"] == "ANSWER_TIMEOUT"
    assert "secret" not in response.text
    assert db.scalar(select(Query)).status == "failed"
    assert db.scalar(select(func.count()).select_from(Answer)) == 0
    assert len(azure_api["calls"]) == 2


def test_missing_llm_config_is_service_unavailable(client, db, settings, ready_source, azure_api):
    source, _, _ = ready_source()
    settings.azure_openai_model = None
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_NOT_CONFIGURED"
    assert db.scalar(select(Query)).status == "failed"
    assert len(azure_api["calls"]) == 1


def test_missing_answer_returns_404(client):
    assert client.get(f"/v1/answers/{uuid4()}").status_code == 404


def test_elapsed_answer_budget_prevents_model_call(
    client, db, ready_source, azure_api, monkeypatch
):
    from unittest.mock import Mock

    from app.answers import service

    source, _, _ = ready_source()
    monkeypatch.setattr(service, "perf_counter", Mock(side_effect=[0.0, 100.0, 101.0]))
    response = client.post(
        "/v1/answers",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "ANSWER_TIMEOUT"
    assert db.scalar(select(Query)).status == "failed"
    assert len(azure_api["calls"]) == 1
