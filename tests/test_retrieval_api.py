from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import Query, RetrievalResult
from app.main import create_app


def test_retrieval_saves_query_rankings_and_source_scope(client, db, ready_source, azure_api):
    source, document, chunks = ready_source()
    other, _, _ = ready_source(["Unselected source must never be returned."])
    response = client.post(
        "/v1/retrieval",
        json={
            "question": "What does Nexus produce?",
            "source_ids": [str(source.id)],
            "top_k": 2,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert [item["chunk_id"] for item in body["chunks"]] == [str(chunk.id) for chunk in chunks]
    assert all(item["source_id"] != str(other.id) for item in body["chunks"])
    query = db.get(Query, UUID(body["query_id"]))
    assert query.status == "completed"
    assert query.completed_at is not None
    assert query.document_id == document.id
    assert query.retrieval_config["embedding_model"] == "text-embedding-3-large"
    results = db.scalars(
        select(RetrievalResult)
        .where(RetrievalResult.query_id == query.id)
        .order_by(RetrievalResult.rank)
    ).all()
    assert [item.rank for item in results] == [1, 2]
    assert results[0].cosine_distance == pytest.approx(0, abs=1e-6)
    assert results[1].cosine_distance > results[0].cosine_distance
    assert all(not result.selected for result in results)
    assert len(azure_api["calls"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "Question", "source_ids": [], "top_k": 0},
        {"question": "Question", "source_ids": [str(uuid4()), str(uuid4())]},
        {"question": "", "source_ids": [str(uuid4())]},
    ],
)
def test_retrieval_rejects_invalid_request_shape(payload):
    response = TestClient(create_app()).post("/v1/retrieval", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize(
    ("question", "top_k", "code"),
    [
        ("  ", 5, "INVALID_QUESTION"),
        ("x" * 4001, 5, "INVALID_QUESTION"),
        ("Question", 21, "INVALID_TOP_K"),
    ],
)
def test_retrieval_rejects_bounds_before_provider(client, db, azure_api, question, top_k, code):
    response = client.post(
        "/v1/retrieval",
        json={
            "question": question,
            "source_ids": [str(uuid4())],
            "top_k": top_k,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert azure_api["calls"] == []
    assert db.scalar(select(func.count()).select_from(Query)) == 0


def test_missing_source_is_not_reported_as_insufficient_context(client, azure_api):
    response = client.post(
        "/v1/retrieval",
        json={
            "question": "Question",
            "source_ids": [str(uuid4())],
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SOURCE_NOT_FOUND"
    assert azure_api["calls"] == []


def test_failed_source_cannot_be_queried(client, db, ready_source, azure_api):
    source, _, _ = ready_source()
    source.status = "failed"
    db.commit()
    response = client.post(
        "/v1/retrieval",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 409
    assert azure_api["calls"] == []


def test_embedding_timeout_saves_failed_query(client, db, ready_source, azure_api):
    source, _, _ = ready_source()
    azure_api["embedding_error"] = httpx.ReadTimeout("private transport details")
    response = client.post(
        "/v1/retrieval",
        json={
            "question": "Question",
            "source_ids": [str(source.id)],
        },
    )
    assert response.status_code == 504
    assert "private" not in response.text
    query = db.get(Query, UUID(response.json()["error"]["query_id"]))
    assert query.status == "failed"
    assert query.error_code == "EMBEDDING_TIMEOUT"
    assert len(azure_api["calls"]) == 1
