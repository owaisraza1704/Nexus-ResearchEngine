import json

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm import azure_openai


class StructuredAnswer(BaseModel):
    answer: str
    citation_ids: list[str]


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-10-21",
        azure_openai_model="gpt-5.6-luna",
    )


def _completion(content, *, refusal=None, finish_reason="stop"):
    return httpx.Response(
        200,
        json={
            "id": "test-completion",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-5.6-luna-test-version",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content, "refusal": refusal},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 9, "total_tokens": 29},
        },
    )


def test_structured_generation_uses_sdk_schema_and_parser(mock_azure) -> None:
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-5.6-luna"
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["max_completion_tokens"] == 2000
        assert request.extensions["timeout"]["read"] == 7
        return _completion('{"answer":"A cited answer.","citation_ids":["C1"]}')

    mock_azure(azure_openai, handler)
    result = azure_openai.generate_structured(
        "Context",
        StructuredAnswer,
        _settings(),
        timeout_seconds=7,
    )
    assert result.parsed == StructuredAnswer(answer="A cited answer.", citation_ids=["C1"])
    assert result.model == "gpt-5.6-luna-test-version"
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 9


@pytest.mark.parametrize(
    "response",
    [
        _completion('{"answer":"Missing citations"}'),
        _completion("not json"),
        _completion(None, refusal="Cannot answer"),
        _completion('{"answer":', finish_reason="length"),
    ],
)
def test_structured_generation_rejects_invalid_or_refused_output(mock_azure, response) -> None:
    mock_azure(azure_openai, lambda request: response)
    with pytest.raises(azure_openai.AzureLLMOutputError):
        azure_openai.generate_structured("Context", StructuredAnswer, _settings())


def test_structured_generation_times_out_without_retry(mock_azure) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    mock_azure(azure_openai, handler)
    with pytest.raises(azure_openai.AzureLLMTimeoutError):
        azure_openai.generate_structured("Context", StructuredAnswer, _settings())
    assert len(calls) == 1


def test_structured_generation_reports_provider_errors_safely(
    mock_azure, caplog, monkeypatch
) -> None:
    # In-process Alembic tests can disable loggers created before their logging setup.
    monkeypatch.setattr(azure_openai.logger, "disabled", False)
    mock_azure(
        azure_openai,
        lambda request: httpx.Response(
            429,
            headers={"x-request-id": "test-provider-request"},
            json={"error": {"message": "private provider detail", "type": "rate_limit"}},
        ),
    )
    with pytest.raises(azure_openai.AzureLLMError, match="request failed") as error:
        azure_openai.generate_structured("Context", StructuredAnswer, _settings())
    assert "private provider detail" not in str(error.value)
    assert "type=RateLimitError status=429 request_id=test-provider-request" in caplog.text
    assert "private provider detail" not in caplog.text
    assert "test-key" not in caplog.text


def test_structured_generation_requires_configuration() -> None:
    with pytest.raises(azure_openai.AzureLLMConfigurationError):
        azure_openai.generate_structured("Context", StructuredAnswer, Settings(_env_file=None))
