import json
from copy import deepcopy
from decimal import Decimal

import pytest

from evals.research import DEFAULT_CASES, evaluate_research, upload_documents


def test_evaluation_uses_actual_rankings_and_reports_separate_contract_checks(
    client, research_sources, research_azure
):
    dataset = json.loads(DEFAULT_CASES.read_text())
    dataset["cases"] = dataset["cases"][:1]
    sources = {
        key: {"source_id": str(source.id), "document_id": str(document.id)}
        for key, (source, document, _) in zip(("alpha", "beta"), research_sources, strict=True)
    }
    report = evaluate_research(client, sources, dataset)
    assert report["pass_count"] == 1
    assert all(value == 1.0 for value in report["check_pass_rates"].values())
    assert report["retrieval_metrics_per_source"]["R@4"] == 1.0
    assert report["query_usage"]["input_tokens"] == 100
    assert report["provider_cost"]["usd"] is None
    assert "do not prove semantic support" in report["support_review"]


def test_bad_gold_labels_fail_before_paid_generation(client, research_sources, research_azure):
    dataset = json.loads(DEFAULT_CASES.read_text())
    dataset["cases"] = dataset["cases"][:1]
    dataset["cases"][0]["gold_passages"]["alpha"] = ["This passage does not exist"]
    sources = {
        key: {"source_id": str(source.id), "document_id": str(document.id)}
        for key, (source, document, _) in zip(("alpha", "beta"), research_sources, strict=True)
    }
    with pytest.raises(ValueError, match="gold label"):
        evaluate_research(client, sources, dataset)
    assert research_azure["calls"] == []


def test_real_evaluation_documents_upload_and_keep_both_formats(client, azure_api):
    dataset = json.loads(DEFAULT_CASES.read_text())
    dataset["documents"] = {key: deepcopy(dataset["documents"][key]) for key in ("alpha", "beta")}
    sources = upload_documents(client, dataset)
    for key, source in sources.items():
        detail = client.get(f"/v1/sources/{source['source_id']}").json()
        assert detail["status"] == "ready"
        assert detail["document"]["chunk_count"] >= 6
        expected = "30 days" if key == "alpha" else "90 days"
        assert expected in detail["normalized_text"]


def test_cost_estimate_uses_explicit_prices_not_invented_deployment_rates(
    client, research_sources, research_azure
):
    dataset = json.loads(DEFAULT_CASES.read_text())
    dataset["cases"] = dataset["cases"][:1]
    sources = {
        key: {"source_id": str(source.id), "document_id": str(document.id)}
        for key, (source, document, _) in zip(("alpha", "beta"), research_sources, strict=True)
    }
    report = evaluate_research(
        client,
        sources,
        dataset,
        prices_per_million={
            "embedding_tokens": Decimal("0.1"),
            "input_tokens": Decimal("1"),
            "output_tokens": Decimal("2"),
        },
    )
    assert report["provider_cost"]["usd"] == "0.0001408"
    assert "not an Azure billing record" in report["provider_cost"]["reason"]
