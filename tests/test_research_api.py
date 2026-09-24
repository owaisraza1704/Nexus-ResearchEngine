from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Document, DocumentChunk
from app.db.research_models import ResearchRun
from app.research.service import create_run


@pytest.mark.parametrize("mode", ["comparison", "synthesis"])
def test_create_status_and_result_are_consistent(
    client, db, research_sources, research_azure, mode
):
    ids = [str(row[0].id) for row in research_sources]
    response = client.post(
        "/v1/research/runs",
        json={
            "question": "Compare retention",
            "mode": mode,
            "source_ids": ids,
            "retrieval": {"top_k_per_source": 1},
            "output": {"max_claims": 4},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == mode
    assert body["status"] == "completed"
    assert {item["source_id"] for item in body["evidence"]} == set(ids)
    assert all(item["excerpt"] and item["locator"] for item in body["evidence"])
    assert len(body["claims"]) == 2
    assert body["contradictions"] == []
    status = client.get(f"/v1/research/runs/{body['run_id']}")
    assert status.status_code == 200
    assert len(status.json()["retrieval_results"]) == 2
    assert "excerpt" not in status.text
    assert status.json()["retrieval"]["top_k_per_source"] == 1
    assert status.json()["output"]["max_claims"] == 4
    assert status.json()["usage"] == body["usage"]
    assert client.get(f"/v1/research/runs/{body['run_id']}/result").json() == body
    assert len(research_azure["calls"]) == 2

    first, _, chunks = research_sources[0]
    newer = Document(
        source_id=first.id,
        version=2,
        status="ready",
        mime_type="application/pdf",
        parser_name="docling",
        parser_version="test",
        normalized_text="New source version.",
    )
    db.add(newer)
    db.flush()
    first.current_document_id = newer.id
    first.display_name = "Changed after completion"
    db.get(DocumentChunk, chunks[0].id).locator = {"changed": True}
    db.commit()
    db.expire_all()
    assert client.get(f"/v1/research/runs/{body['run_id']}/result").json() == body


def test_candidate_contradiction_is_exposed(client, research_sources, research_azure):
    research_azure["answer"]["claims"][0]["support_status"] = "contradicted"
    research_azure["answer"]["claims"][0]["evidence"].append(
        {
            "evidence_id": "E2",
            "relationship": "contradicts",
            "explanation": "Candidate disagreement.",
        }
    )
    body = client.post(
        "/v1/research/runs",
        json={
            "question": "Compare retention",
            "source_ids": [str(row[0].id) for row in research_sources],
        },
    ).json()
    assert body["contradictions"][0]["status"] == "candidate"
    assert body["contradictions"][0]["supporting_evidence"] == ["E1"]
    assert body["contradictions"][0]["contradicting_evidence"] == ["E2"]
    assert "conflict" in {gap["reason"] for gap in body["gaps"]}


@pytest.mark.parametrize(
    "payload,code,status",
    [
        ({"source_ids": []}, "SOURCE_SET_TOO_SMALL", 422),
        ({"source_ids": [str(uuid4())]}, "SOURCE_SET_TOO_SMALL", 422),
        ({"source_ids": [str(uuid4()) for _ in range(6)]}, "SOURCE_SET_TOO_LARGE", 422),
        ({"source_ids": [str(uuid4()), str(uuid4())]}, "SOURCE_NOT_FOUND", 404),
        ({"mode": "autonomous"}, "INVALID_REQUEST", 422),
        ({"retrieval": {"top_k_per_source": 21}}, "RESEARCH_LIMIT_EXCEEDED", 422),
        ({"output": {"max_claims": 13}}, "RESEARCH_LIMIT_EXCEEDED", 422),
        ({"question": "  "}, "INVALID_QUESTION", 422),
        ({"question": "x" * 4001}, "INVALID_QUESTION", 422),
        ({"unrecognized": True}, "INVALID_REQUEST", 422),
    ],
)
def test_bad_requests_fail_before_provider_calls(
    client, research_sources, research_azure, payload, code, status
):
    request = {
        "question": "Compare",
        "source_ids": [str(row[0].id) for row in research_sources],
        **payload,
    }
    response = client.post("/v1/research/runs", json=request)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert research_azure["calls"] == []


def test_failed_run_is_inspectable_but_has_no_success_result(
    client, research_sources, research_azure
):
    research_azure["chat_error"] = httpx.ReadTimeout("sensitive transport detail")
    response = client.post(
        "/v1/research/runs",
        json={"question": "Compare", "source_ids": [str(row[0].id) for row in research_sources]},
    )
    assert response.status_code == 504
    error = response.json()["error"]
    assert "sensitive" not in response.text
    status = client.get(f"/v1/research/runs/{error['run_id']}").json()
    assert status["status"] == "failed"
    assert len(status["sources"]) == 2
    result = client.get(f"/v1/research/runs/{error['run_id']}/result")
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "RESEARCH_RUN_FAILED"


def test_missing_and_unfinished_runs_are_explicit(client, db, settings, research_sources):
    missing = str(uuid4())
    for path in (f"/v1/research/runs/{missing}", f"/v1/research/runs/{missing}/result"):
        assert client.get(path).status_code == 404
    run = create_run(db, "Compare", [row[0].id for row in research_sources], settings)
    response = client.get(f"/v1/research/runs/{run.id}/result")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RESEARCH_RESULT_NOT_READY"
    assert db.scalar(select(ResearchRun.status)) == "created"
