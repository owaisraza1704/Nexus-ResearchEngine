from dataclasses import dataclass
from typing import Generic, TypeVar

from openai import (
    APIError,
    APITimeoutError,
    AzureOpenAI,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
)
from pydantic import BaseModel, ValidationError

from app.config import Settings

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


class AzureLLMConfigurationError(ValueError):
    """Raised when Azure OpenAI text-generation settings are incomplete."""


class AzureLLMError(RuntimeError):
    """Raised when Azure OpenAI cannot return generated text."""


class AzureLLMTimeoutError(AzureLLMError):
    """The bounded model request timed out."""


class AzureLLMOutputError(AzureLLMError):
    """The model refused or returned an incomplete or invalid response."""


@dataclass(frozen=True)
class StructuredGenerationResult(Generic[StructuredOutputT]):
    parsed: StructuredOutputT
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


def generate_structured(
    prompt: str,
    response_model: type[StructuredOutputT],
    settings: Settings,
    *,
    instructions: str | None = None,
    timeout_seconds: float | None = None,
) -> StructuredGenerationResult[StructuredOutputT]:
    """Generate a Pydantic-validated response using Azure OpenAI."""

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
        with AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=timeout_seconds or settings.provider_timeout_seconds,
            max_retries=0,
        ) as client:
            response = client.chat.completions.parse(
                model=deployment,
                messages=messages,
                response_format=response_model,
                max_completion_tokens=settings.max_answer_tokens,
            )
    except APITimeoutError as exc:
        raise AzureLLMTimeoutError("Azure OpenAI answer request timed out") from exc
    except (ValidationError, LengthFinishReasonError, ContentFilterFinishReasonError) as exc:
        raise AzureLLMOutputError("Azure OpenAI returned an invalid or incomplete answer") from exc
    except APIError as exc:
        raise AzureLLMError("Azure OpenAI structured-generation request failed") from exc

    choices = list(getattr(response, "choices", ()))
    if not choices:
        raise AzureLLMOutputError("Azure OpenAI returned no structured-generation choices")

    parsed = getattr(choices[0].message, "parsed", None)
    if parsed is None:
        raise AzureLLMOutputError("Azure OpenAI refused or returned no structured output")

    usage = getattr(response, "usage", None)
    return StructuredGenerationResult(
        parsed=parsed,
        model=str(getattr(response, "model", deployment)),
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
    )


def _required_setting(value: str | None, name: str) -> str:
    if not value:
        raise AzureLLMConfigurationError(f"Missing setting: {name}")
    return value
