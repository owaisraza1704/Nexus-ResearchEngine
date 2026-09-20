from dataclasses import dataclass

from openai import AzureOpenAI

from app.config import Settings


class AzureEmbeddingConfigurationError(ValueError):
    """Raised when Azure OpenAI embedding settings are incomplete."""


class AzureEmbeddingError(RuntimeError):
    """Raised when Azure OpenAI cannot return a valid embedding."""


@dataclass(frozen=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    model: str
    prompt_tokens: int | None


def embed_text(text: str, settings: Settings) -> EmbeddingResult:
    """Create one embedding using the configured Azure OpenAI deployment."""

    if not text.strip():
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
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        response = client.embeddings.create(input=[text], model=deployment)
        embedding = tuple(float(value) for value in response.data[0].embedding)
    except Exception as exc:
        raise AzureEmbeddingError("Azure OpenAI embedding request failed") from exc

    if len(embedding) != settings.azure_openai_embedding_dimensions:
        raise AzureEmbeddingError(
            "Azure OpenAI returned an unexpected embedding dimension: "
            f"expected {settings.azure_openai_embedding_dimensions}, got {len(embedding)}"
        )

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    model = str(getattr(response, "model", deployment))
    return EmbeddingResult(
        vector=embedding,
        model=model,
        prompt_tokens=prompt_tokens,
    )


def _required_setting(value: str | None, name: str) -> str:
    if not value:
        raise AzureEmbeddingConfigurationError(f"Missing setting: {name}")
    return value
