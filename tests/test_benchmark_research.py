import importlib

import httpx
import pytest


@pytest.fixture
def benchmark(monkeypatch):
    monkeypatch.syspath_prepend("scripts")
    return importlib.import_module("benchmark_research")


def test_benchmark_accepts_a_valid_report_with_explicit_gaps(benchmark):
    start, end = "2026-09-26T00:00:00+00:00", "2026-09-26T00:00:01+00:00"
    evidence = [
        {
            "source_id": source,
            "chunk_id": source,
            "document_id": source,
            "excerpt": "Source evidence",
            "locator": {"page": 1},
        }
        for source in ("alpha", "beta")
    ]
    result = {
        "outcome": "completed",
        "claims": [{}],
        "citations": [{}, {}],
        "evidence": evidence,
        "source_coverage": [{"document_id": "alpha"}, {"document_id": "beta"}],
        "gaps": [{"reason": "no_evidence"}],
        "usage": {},
        "budget": {},
        "model": "test",
    }

    def response(request):
        path = request.url.path
        if request.method == "POST":
            body = {"job_id": "test-job"}
        elif path.endswith("/result"):
            body = result
        elif path.endswith("/tasks"):
            body = {
                "tasks": [
                    {
                        "key": "retrieve",
                        "type": "retrieve_internal",
                        "state": "succeeded",
                        "started_at": start,
                        "completed_at": end,
                        "attempt_count": 1,
                    }
                ]
            }
        elif path.endswith("/plan"):
            body = {"graph_hash": "test-plan", "tasks": []}
        elif "/chunks/" in path:
            body = {"text": "Source evidence", "locator": {"page": 1}}
        else:
            body = {"status": "completed_with_gaps", "created_at": start, "completed_at": end}
        return httpx.Response(200, json=body)

    with httpx.Client(base_url="http://test", transport=httpx.MockTransport(response)) as client:
        sample = benchmark.measure(client, "project", ["alpha", "beta"], 1)
    assert sample["status"] == "completed_with_gaps"
    assert sample["citation_integrity_passed"] and sample["gaps"] == 1
    assert sample["backend_ms"] == 1000


def test_benchmark_does_not_hide_a_parallel_slowdown(benchmark):
    samples = [
        {
            "max_parallel_tasks": parallelism,
            "backend_ms": duration,
            "retrieval_tasks_overlapped": parallelism == 2,
            "plan_hash": "test",
        }
        for parallelism, duration in ((1, 100), (2, 120), (2, 120), (1, 100))
    ]
    summary = benchmark.summarize(samples)
    assert summary["observed_median_reduction_percent"] == -20
    assert summary["samples_per_variant"] == 2
