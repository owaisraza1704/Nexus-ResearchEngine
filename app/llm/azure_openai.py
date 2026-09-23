from dataclasses import dataclass

from openai import AzureOpenAI

from app.config import Settings


class AzureLLMConfigurationError(ValueError):
    """Raised when Azure OpenAI text-generation settings are incomplete."""


class AzureLLMError(RuntimeError):
    """Raised when Azure OpenAI cannot return generated text."""


@dataclass(frozen=True)
class TextGenerationResult:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


def generate_text(
    prompt: str,
    settings: Settings,
    *,
    instructions: str | None = None,
) -> TextGenerationResult:
    """Generate text using the configured Azure OpenAI chat deployment."""

    if not prompt.strip():
        raise ValueError("Cannot generate text from an empty prompt")

    endpoint = _required_setting(settings.azure_openai_endpoint, "azure_openai_endpoint")
    api_key = _required_setting(settings.azure_openai_api_key, "azure_openai_api_key")
    api_version = _required_setting(
        settings.azure_openai_api_version,
        "azure_openai_api_version",
    )
    deployment = _required_setting(settings.azure_openai_model, "azure_openai_model")

    messages: list[dict[str, str]] = []
    if instructions and instructions.strip():
        messages.append({"role": "system", "content": instructions})
    messages.append({"role": "user", "content": prompt})

    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
        )
    except Exception as exc:
        raise AzureLLMError("Azure OpenAI text-generation request failed") from exc

    choices = list(getattr(response, "choices", ()))
    if not choices:
        raise AzureLLMError("Azure OpenAI returned no text-generation choices")

    text = getattr(choices[0].message, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise AzureLLMError("Azure OpenAI returned empty generated text")

    usage = getattr(response, "usage", None)
    return TextGenerationResult(
        text=text,
        model=str(getattr(response, "model", deployment)),
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
    )


def _required_setting(value: str | None, name: str) -> str:
    if not value:
        raise AzureLLMConfigurationError(f"Missing setting: {name}")
    return value
