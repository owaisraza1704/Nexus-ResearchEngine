import json

import httpx
import pytest

from app.config import Settings
from app.embeddings import azure_openai


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-10-21",
        azure_openai_embedding_deployment="embedding-large",
        azure_openai_embedding_dimensions=3,
    )


def _response(vectors):
    return httpx.Response(
        200,
        json={
            "object": "list",
            "model": "embedding-large-version",
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in vectors
            ],
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        },
    )


def test_embed_text_maps_sdk_request_and_response(mock_azure) -> None:
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "embedding-large"
        assert payload["input"] == ["research text"]
        return _response([(0, [0.1, 0.2, 0.3])])

    mock_azure(azure_openai, handler)
    result = azure_openai.embed_text("research text", _settings())
    assert result.vector == (0.1, 0.2, 0.3)
    assert result.model == "embedding-large-version"
    assert result.deployment == "embedding-large"
    assert result.prompt_tokens == 4


def test_embed_texts_sorts_batch_results(mock_azure) -> None:
    mock_azure(
        azure_openai,
        lambda request: _response(
            [
                (1, [0.4, 0.5, 0.6]),
                (0, [0.1, 0.2, 0.3]),
            ]
        ),
    )
    results = azure_openai.embed_texts(["first", "second"], _settings())
    assert [result.vector for result in results] == [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6)]


@pytest.mark.parametrize("vectors", [[(0, [0.1, 0.2])], []])
def test_embed_text_rejects_wrong_dimensions_or_count(mock_azure, vectors) -> None:
    mock_azure(azure_openai, lambda request: _response(vectors))
    with pytest.raises(azure_openai.AzureEmbeddingError):
        azure_openai.embed_text("research text", _settings())


def test_embed_text_requires_configuration() -> None:
    with pytest.raises(azure_openai.AzureEmbeddingConfigurationError):
        azure_openai.embed_text("research text", Settings(_env_file=None))


def test_embed_text_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="empty text"):
        azure_openai.embed_text("  ", _settings())


def test_embedding_timeout_is_explicit_and_not_retried(mock_azure) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    mock_azure(azure_openai, handler)
    with pytest.raises(azure_openai.AzureEmbeddingTimeoutError):
        azure_openai.embed_text("research text", _settings())
    assert len(calls) == 1
