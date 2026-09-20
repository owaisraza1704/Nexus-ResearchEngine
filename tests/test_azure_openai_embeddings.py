from types import SimpleNamespace

import pytest

from app.config import Settings
from app.embeddings import azure_openai
from app.embeddings.azure_openai import (
    AzureEmbeddingConfigurationError,
    AzureEmbeddingError,
    embed_text,
)


def _settings() -> Settings:
    return Settings(
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-10-21",
        azure_openai_embedding_deployment="embedding-large",
        azure_openai_embedding_dimensions=3,
    )


def test_embed_text_maps_azure_sdk_request_and_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.update(kwargs)
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
                model="embedding-large",
                usage=SimpleNamespace(prompt_tokens=4),
            )

    class FakeAzureOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.update(kwargs)
            self.embeddings = FakeEmbeddings()

    monkeypatch.setattr(azure_openai, "AzureOpenAI", FakeAzureOpenAI)

    result = embed_text("research text", _settings())

    assert calls["api_key"] == "test-key"
    assert calls["azure_endpoint"] == "https://example.openai.azure.com/"
    assert calls["api_version"] == "2024-10-21"
    assert calls["model"] == "embedding-large"
    assert calls["input"] == ["research text"]
    assert result.vector == (0.1, 0.2, 0.3)
    assert result.model == "embedding-large"
    assert result.prompt_tokens == 4


def test_embed_text_requires_azure_settings() -> None:
    with pytest.raises(AzureEmbeddingConfigurationError, match="azure_openai_endpoint"):
        embed_text("research text", Settings(_env_file=None))


def test_embed_text_rejects_unexpected_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAzureOpenAI:
        def __init__(self, **kwargs: object) -> None:
            del kwargs
            self.embeddings = SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    data=[SimpleNamespace(embedding=[0.1, 0.2])],
                    model="embedding-large",
                    usage=None,
                )
            )

    monkeypatch.setattr(azure_openai, "AzureOpenAI", FakeAzureOpenAI)

    with pytest.raises(AzureEmbeddingError, match="unexpected embedding dimension"):
        embed_text("research text", _settings())


def test_embed_text_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="empty text"):
        embed_text("  ", _settings())
