from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import retrieval as retrieval_api
from app.config import Settings
from app.main import app
from app.retrieval.vector_search import RetrievedChunk


def test_retrieval_endpoint_embeds_and_returns_ranked_chunks(monkeypatch) -> None:
    database = object()
    settings = Settings()
    source_id = uuid4()
    chunk = RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        source_id=source_id,
        sequence=2,
        text="Relevant research text",
        locator={"page": 3},
        cosine_distance=0.17,
    )
    calls = {}

    def fake_retrieve_question(
        value_db,
        question,
        source_ids,
        value_settings,
        *,
        top_k,
    ):
        calls.update(
            {
                "db": value_db,
                "question": question,
                "source_ids": source_ids,
                "settings": value_settings,
                "top_k": top_k,
            }
        )
        return (chunk,)

    monkeypatch.setattr(retrieval_api, "retrieve_question", fake_retrieve_question)
    app.dependency_overrides[retrieval_api.get_db] = lambda: database
    app.dependency_overrides[retrieval_api.get_settings] = lambda: settings

    try:
        response = TestClient(app).post(
            "/v1/retrieval",
            json={
                "question": "What is relevant?",
                "source_ids": [str(source_id)],
                "top_k": 3,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "chunks": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "document_id": str(chunk.document_id),
                    "source_id": str(chunk.source_id),
                    "sequence": 2,
                    "text": "Relevant research text",
                    "locator": {"page": 3},
                    "cosine_distance": 0.17,
                }
            ]
        }
        assert calls == {
            "db": database,
            "question": "What is relevant?",
            "source_ids": [source_id],
            "settings": settings,
            "top_k": 3,
        }
    finally:
        app.dependency_overrides.clear()


def test_retrieval_endpoint_rejects_non_positive_top_k() -> None:
    response = TestClient(app).post(
        "/v1/retrieval",
        json={"question": "What is relevant?", "source_ids": [], "top_k": 0},
    )

    assert response.status_code == 422
