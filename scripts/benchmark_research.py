"""Opt-in real Azure benchmark: identical source inputs, sequential vs parallel Celery jobs.

Creates a synthetic workspace and keeps every run. No injected delays, mocked providers,
application prompt cache, or selected 'best' timing. Model-generated plans may differ.
"""

import argparse
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from statistics import median
from time import monotonic

import httpx
from smoke_documents import make_documents
from smoke_local import wait_for

QUESTION = (
    "Produce a comprehensive cited comparison of Alpha and Beta. Investigate their record "
    "retention periods and request execution approaches as separate aspects; summarize "
    "agreements, differences, and what the sources do not tell us."
)


def measure(client, project_id, source_ids, parallelism):
    started = monotonic()
    job = (
        client.post(
            "/v1/research/jobs",
            json={
                "workspace_id": project_id,
                "source_ids": source_ids,
                "mode": "agentic",
                "question": QUESTION,
                "retrieval_strategy": "hybrid",
                "top_k_per_source": 4,
                "budget": {"max_parallel_tasks": parallelism},
            },
        )
        .raise_for_status()
        .json()
    )
    path = f"/v1/research/jobs/{job['job_id']}"
    settled = wait_for(
        client,
        path,
        lambda body: (
            body["status"]
            in {
                "completed",
                "completed_with_gaps",
                "failed",
                "cancelled",
            }
        ),
    )
    elapsed = round((monotonic() - started) * 1000)
    assert settled["status"] in {"completed", "completed_with_gaps"}, settled
    result = client.get(path + "/result").raise_for_status().json()
    tasks = client.get(path + "/tasks").raise_for_status().json()["tasks"]
    plan = client.get(path + "/plan").raise_for_status().json()
    assert result["outcome"] == "completed" and result["claims"] and result["citations"], result
    cited = {item["source_id"] for item in result["evidence"]}
    assert cited == set(source_ids), "The report must retain evidence from both benchmark sources"
    for item in result["evidence"]:
        chunk = (
            client.get(
                f"/v1/projects/{project_id}/sources/{item['source_id']}/chunks/{item['chunk_id']}",
                params={"document_id": item["document_id"]},
            )
            .raise_for_status()
            .json()
        )
        assert chunk["text"] == item["excerpt"] and chunk["locator"] == item["locator"]
    branches = [task for task in tasks if task["type"] == "retrieve_internal"]
    overlap = any(
        max(datetime.fromisoformat(a["started_at"]), datetime.fromisoformat(b["started_at"]))
        < min(datetime.fromisoformat(a["completed_at"]), datetime.fromisoformat(b["completed_at"]))
        for a, b in combinations(branches, 2)
    )
    backend_ms = round(
        (
            datetime.fromisoformat(settled["completed_at"])
            - datetime.fromisoformat(settled["created_at"])
        ).total_seconds()
        * 1000
    )
    return {
        "job_id": job["job_id"],
        "status": settled["status"],
        "max_parallel_tasks": parallelism,
        "backend_ms": backend_ms,
        "client_elapsed_ms": elapsed,
        "plan_hash": plan["graph_hash"],
        "plan": plan["tasks"],
        "retrieval_branch_count": len(branches),
        "retrieval_tasks_overlapped": overlap,
        "tasks": [
            {
                key: task[key]
                for key in (
                    "key",
                    "type",
                    "state",
                    "started_at",
                    "completed_at",
                    "attempt_count",
                )
            }
            for task in tasks
        ],
        "usage": result["usage"],
        "budget": result["budget"],
        "model": result["model"],
        "claims": len(result["claims"]),
        "citations": len(result["citations"]),
        "gaps": len(result["gaps"]),
        "source_snapshots": [item["document_id"] for item in result["source_coverage"]],
        "citation_integrity_passed": True,
    }


def summarize(samples):
    sequential = [sample["backend_ms"] for sample in samples if sample["max_parallel_tasks"] == 1]
    parallel = [sample["backend_ms"] for sample in samples if sample["max_parallel_tasks"] == 2]
    baseline, candidate = median(sequential), median(parallel)
    return {
        "samples_per_variant": len(sequential),
        "sequential_median_ms": baseline,
        "parallel_median_ms": candidate,
        "observed_median_reduction_percent": round((baseline - candidate) / baseline * 100, 2),
        "parallel_overlap_observed": any(
            sample["retrieval_tasks_overlapped"]
            for sample in samples
            if sample["max_parallel_tasks"] == 2
        ),
        "distinct_plan_hashes": len({sample["plan_hash"] for sample in samples}),
        "limitation": "Small synthetic corpus; model plans/output lengths and Azure latency vary. "
        "This is an end-to-end observation, not proof of a universal or causal 50% speedup. "
        "Citation identity was checked; semantic quality still requires review.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.pairs < 2:
        parser.error("Use at least two measured pairs; warm-ups are recorded separately.")
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION,
        "method": "One warm-up per variant, then alternating sequential/parallel pairs. "
        "Only max_parallel_tasks changes. Ingestion is excluded; planning, queueing, retrieval, "
        "generation and validation are included. No application prompt cache.",
        "warmups": [],
        "samples": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(base_url=args.api, timeout=30) as client:
            system = client.get("/v1/system").raise_for_status().json()
            assert system["queue_backend"] == "celery" and system["worker_count"] > 0
            assert system["limits"]["max_parallel_tasks"] >= 2
            report["configuration"] = {
                key: system[key]
                for key in (
                    "model",
                    "embedding_deployment",
                    "embedding_dimensions",
                    "queue_backend",
                )
            }
            project = (
                client.post(
                    "/v1/projects",
                    json={
                        "title": "Sequential vs parallel research benchmark",
                        "description": "Synthetic sources; measured and warm-up runs are retained.",
                    },
                )
                .raise_for_status()
                .json()
            )
            report["project_id"] = project["id"]
            print(json.dumps({"project_id": project["id"]}), flush=True)
            source_ids = []
            for name, content in make_documents():
                source = (
                    client.post(
                        f"/v1/projects/{project['id']}/sources/uploads",
                        files={"file": (name, content)},
                    )
                    .raise_for_status()
                    .json()
                )
                source_ids.append(source["source_id"])
            ready = wait_for(
                client,
                f"/v1/projects/{project['id']}",
                lambda body: all(
                    source["status"] in {"ready", "failed"} for source in body["sources"]
                ),
            )
            assert all(source["status"] == "ready" for source in ready["sources"])
            for parallelism in (1, 2):
                report["warmups"].append(measure(client, project["id"], source_ids, parallelism))
                print(json.dumps({"warmup": parallelism}), flush=True)
            for pair in range(args.pairs):
                order = (1, 2) if pair % 2 == 0 else (2, 1)
                for parallelism in order:
                    sample = measure(client, project["id"], source_ids, parallelism)
                    report["samples"].append({"pair": pair + 1, **sample})
                    print(
                        json.dumps(
                            {
                                key: sample[key]
                                for key in (
                                    "job_id",
                                    "max_parallel_tasks",
                                    "backend_ms",
                                    "retrieval_tasks_overlapped",
                                )
                            }
                        ),
                        flush=True,
                    )
            report["summary"] = summarize(report["samples"])
            print(json.dumps(report["summary"]), flush=True)
    finally:
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
