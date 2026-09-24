from collections.abc import Sequence
from dataclasses import dataclass

from openai import APIError, APITimeoutError, AzureOpenAI

from app.config import Settings


class AzureEmbeddingConfigurationError(ValueError):
    """Raised when Azure OpenAI embedding settings are incomplete."""


class AzureEmbeddingError(RuntimeError):
    """Raised when Azure OpenAI cannot return a valid embedding."""


class AzureEmbeddingTimeoutError(AzureEmbeddingError):
    """The bounded embedding request timed out."""


@dataclass(frozen=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    model: str
    deployment: str
    prompt_tokens: int | None


def embed_text(text: str, settings: Settings) -> EmbeddingResult:
    """Create one embedding using the configured Azure OpenAI deployment."""

    return embed_texts([text], settings)[0]


def embed_texts(texts: Sequence[str], settings: Settings) -> tuple[EmbeddingResult, ...]:
    """Create embeddings for a batch of texts using Azure OpenAI."""

    text_values = tuple(texts)
    if not text_values:
        raise ValueError("Cannot embed an empty batch")
    if any(not text.strip() for text in text_values):
        raise ValueError("Cannot embed empty text")

    endpoint = _required_setting(settings.azure_openai_endpoint, "azure_openai_endpoint")
    api_key = _required_setting(settings.azure_openai_api_key, "azure_openai_api_key")
    api_version = _required_setting(
        settings.azure_openai_api_version,
        "azure_openai_api_version",
    )
    deployment = _required_setting(
        settings.azure_openai_embedding_deployment,
        "azure_openai_embedding_deployment",
    )

    try:
        with AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=settings.provider_timeout_seconds,
            max_retries=0,
        ) as client:
            response = client.embeddings.create(
                input=list(text_values),
                model=deployment,
                encoding_format="float",
            )
            response_data = list(response.data)
    except APITimeoutError as exc:
        raise AzureEmbeddingTimeoutError("Azure OpenAI embedding request timed out") from exc
    except APIError as exc:
        raise AzureEmbeddingError("Azure OpenAI embedding request failed") from exc

    if len(response_data) != len(text_values):
        raise AzureEmbeddingError(
            "Azure OpenAI returned an unexpected number of embeddings: "
            f"expected {len(text_values)}, got {len(response_data)}"
        )

    if all(getattr(item, "index", None) is not None for item in response_data):
        response_data.sort(key=lambda item: item.index)

    usage = getattr(response, "usage", None)
    model = str(getattr(response, "model", deployment))
    prompt_tokens = getattr(usage, "prompt_tokens", None) if len(text_values) == 1 else None

    results: list[EmbeddingResult] = []
    for item in response_data:
        embedding = tuple(float(value) for value in item.embedding)
        if len(embedding) != settings.azure_openai_embedding_dimensions:
            raise AzureEmbeddingError(
                "Azure OpenAI returned an unexpected embedding dimension: "
                f"expected {settings.azure_openai_embedding_dimensions}, got {len(embedding)}"
            )
        results.append(
            EmbeddingResult(
                vector=embedding,
                model=model,
                deployment=deployment,
                prompt_tokens=prompt_tokens,
            )
        )

    return tuple(results)


def _required_setting(value: str | None, name: str) -> str:
    if not value:
        raise AzureEmbeddingConfigurationError(f"Missing setting: {name}")
    return value
