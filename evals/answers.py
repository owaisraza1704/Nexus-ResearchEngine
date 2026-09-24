"""Run a small live API check and print cited passages for a separate support review."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import httpx

DEFAULT_CASES = Path(__file__).with_name("answer_cases.json")


def evaluate_answers(client: httpx.Client, source_id: str, dataset: dict) -> dict:
    source_response = client.get(f"/v1/sources/{source_id}")
    source_response.raise_for_status()
    source = source_response.json()
    if source["content_sha256"] != dataset["source_content_sha256"]:
        raise ValueError("The selected source does not match the answer fixture dataset")

    cases = []
    for case in dataset["cases"]:
        started = perf_counter()
        response = client.post(
            "/v1/answers",
            json={
                "question": case["question"],
                "source_ids": [source_id],
                "retrieval": {"top_k": 5},
            },
        )
        elapsed_ms = round((perf_counter() - started) * 1000)
        body = response.json()
        evidence = []
        checks_passed = False
        if response.status_code == 200:
            document_id = source["current_document_id"]
            chunks = {}
            offset = 0
            while True:
                page_response = client.get(
                    f"/v1/sources/{source_id}/chunks",
                    params={
                        "document_id": document_id,
                        "limit": 200,
                        "offset": offset,
                    },
                )
                page_response.raise_for_status()
                page = page_response.json()
                chunks.update({chunk["chunk_id"]: chunk for chunk in page["chunks"]})
                offset += len(page["chunks"])
                if offset >= page["total"]:
                    break
            for citation in body["citations"]:
                chunk = chunks.get(citation["chunk_id"])
                evidence.append(
                    {
                        "label": citation["label"],
                        "valid": bool(
                            chunk
                            and citation["locator"] == chunk["locator"]
                            and citation["source_id"] == source_id
                            and citation["document_id"] == document_id
                        ),
                        "sequence": chunk["sequence"] if chunk else None,
                        "text": chunk["text"] if chunk else None,
                        "display_text": citation["display_text"],
                    }
                )
            reload_response = client.get(f"/v1/answers/{body['answer_id']}")
            checks_passed = (
                body["status"] == case["expected_status"]
                and all(item["valid"] for item in evidence)
                and bool(evidence) == (body["status"] == "completed")
                and reload_response.status_code == 200
                and reload_response.json() == body
            )
        cases.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected_status": case["expected_status"],
                "http_status": response.status_code,
                "contract_checks_passed": checks_passed,
                "http_duration_ms": elapsed_ms,
                "response": body,
                "cited_evidence": evidence,
            }
        )
    return {
        "source_id": source_id,
        "case_count": len(cases),
        "contract_pass_count": sum(case["contract_checks_passed"] for case in cases),
        "support_review": "Review cited_evidence manually; contract checks do not prove support.",
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    dataset = json.loads(args.cases.read_text())
    with httpx.Client(base_url=args.base_url, timeout=100) as client:
        report = evaluate_answers(client, args.source_id, dataset)
    print(json.dumps(report, indent=2))
    if report["contract_pass_count"] != report["case_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
