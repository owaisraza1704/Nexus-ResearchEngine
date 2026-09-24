"""Opt-in real Azure verification. Creates a named workspace; never deletes existing data."""

import argparse
import json
from time import monotonic, sleep

import httpx
from smoke_documents import make_documents


def wait_for(client, path, settled, timeout=650):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        response = client.get(path)
        response.raise_for_status()
        body = response.json()
        if settled(body):
            return body
        sleep(1)
    raise AssertionError(f"Timed out waiting for {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--web", action="store_true", help="Also acquire the public example.com page"
    )
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, timeout=30) as client:
        system = client.get("/v1/system").raise_for_status().json()
        assert system["worker_count"] > 0, "Start the local worker first"
        assert system["azure_configured"], "Configure Azure first"
        workspace = (
            client.post(
                "/v1/projects",
                json={
                    "title": "MVP3 verification — retention policies",
                    "description": (
                        "Synthetic PDF and DOCX fixtures for checking the complete local product."
                    ),
                },
            )
            .raise_for_status()
            .json()
        )
        project_id = workspace["id"]
        print(json.dumps({"project_id": project_id}), flush=True)
        source_ids = []
        for name, content in make_documents():
            uploaded = (
                client.post(
                    f"/v1/projects/{project_id}/sources/uploads", files={"file": (name, content)}
                )
                .raise_for_status()
                .json()
            )
            source_ids.append(uploaded["source_id"])
        workspace = wait_for(
            client,
            f"/v1/projects/{project_id}",
            lambda body: all(source["status"] in {"ready", "failed"} for source in body["sources"]),
        )
        assert all(source["status"] == "ready" for source in workspace["sources"]), workspace
        print(
            json.dumps(
                {
                    "uploaded_sources": source_ids,
                    "statuses": [s["status"] for s in workspace["sources"]],
                }
            ),
            flush=True,
        )
        cases = [
            ("answer", "How long does Alpha retain records?", source_ids[:1]),
            (
                "comparison",
                "Compare the retention periods and request execution in Alpha and Beta.",
                source_ids,
            ),
            (
                "synthesis",
                "Summarize the retention policies and execution approaches in Alpha and Beta.",
                source_ids,
            ),
            ("evidence", "What are the retention periods?", source_ids),
            (
                "agentic",
                "Compare Alpha and Beta retention periods and synchronous versus "
                "asynchronous request execution.",
                source_ids,
            ),
            ("answer", "What exact year did Alpha open an office on Mars?", source_ids[:1]),
        ]
        jobs = []
        for index, (mode, question, selected) in enumerate(cases):
            job = (
                client.post(
                    "/v1/research/jobs",
                    json={
                        "workspace_id": project_id,
                        "question": question,
                        "source_ids": selected,
                        "mode": mode,
                        "idempotency_key": f"verification-{index}",
                    },
                )
                .raise_for_status()
                .json()
            )
            path = f"/v1/research/jobs/{job['job_id']}"
            print(
                json.dumps({"mode": mode, "job_id": job["job_id"], "status": job["status"]}),
                flush=True,
            )
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
            assert settled["status"] in {"completed", "completed_with_gaps"}, settled
            result = client.get(path + "/result").raise_for_status().json()
            if index == 5:
                assert result["outcome"] == "insufficient_context", result
            elif mode != "evidence":
                assert result["outcome"] == "completed", result
                assert "30" in result["summary"] or any(
                    "30" in claim["text"] for claim in result["claims"]
                ), result
            for evidence in result["evidence"]:
                assert evidence["source_id"] in selected
                chunk = (
                    client.get(
                        f"/v1/projects/{project_id}/sources/{evidence['source_id']}/chunks/{evidence['chunk_id']}",
                        params={"document_id": evidence["document_id"]},
                    )
                    .raise_for_status()
                    .json()
                )
                assert chunk["text"] == evidence["excerpt"]
                assert chunk["locator"] == evidence["locator"]
            assert (
                client.get(path + "/export?format=json").raise_for_status().json()["result_id"]
                == result["result_id"]
            )
            jobs.append(
                {
                    "job_id": job["job_id"],
                    "mode": mode,
                    "status": result["status"],
                    "outcome": result["outcome"],
                    "claims": len(result["claims"]),
                    "citations": len(result["citations"]),
                    "provider_calls": result["budget"]["used_provider_calls"],
                }
            )
            print(json.dumps(jobs[-1]), flush=True)
        if args.web:
            job = (
                client.post(
                    "/v1/research/jobs",
                    json={
                        "workspace_id": project_id,
                        "question": "What is this example domain for?",
                        "mode": "evidence",
                        "policy": {
                            "allow_web": True,
                            "allowed_domains": ["example.com"],
                            "web_urls": ["https://example.com/"],
                        },
                    },
                )
                .raise_for_status()
                .json()
            )
            path = f"/v1/research/jobs/{job['job_id']}"
            settled = wait_for(
                client,
                path,
                lambda body: body["status"] in {"completed", "completed_with_gaps", "failed"},
            )
            assert settled["status"] == "completed", settled
            result = client.get(path + "/result").raise_for_status().json()
            assert result["external_sources"][0]["url"] == "https://example.com/"
            assert result["evidence"][0]["locator"]["content_sha256"]
            print(json.dumps({"web_job_id": job["job_id"], "status": result["status"]}), flush=True)
        print(json.dumps({"verified_project": project_id, "jobs": jobs}), flush=True)


if __name__ == "__main__":
    main()
