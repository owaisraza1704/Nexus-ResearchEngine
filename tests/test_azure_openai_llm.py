from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import azure_openai


def _settings() -> Settings:
    return Settings(
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-10-21",
        azure_openai_model="gpt-5.6-luna",
    )


def test_generate_text_uses_configured_azure_chat_deployment(monkeypatch) -> None:
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(
                model="gpt-5.6-luna",
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Generated answer")
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
            )

    class FakeAzureOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(azure_openai, "AzureOpenAI", FakeAzureOpenAI)

    result = azure_openai.generate_text(
        "Use only the supplied context.",
        _settings(),
        instructions="Answer with citations.",
    )

    assert result == azure_openai.TextGenerationResult(
        text="Generated answer",
        model="gpt-5.6-luna",
        prompt_tokens=12,
        completion_tokens=7,
    )
    assert calls == {
        "client": {
            "api_key": "test-key",
            "azure_endpoint": "https://example.openai.azure.com/",
            "api_version": "2024-10-21",
        },
        "model": "gpt-5.6-luna",
        "messages": [
            {"role": "system", "content": "Answer with citations."},
            {"role": "user", "content": "Use only the supplied context."},
        ],
    }


def test_generate_text_requires_a_chat_model() -> None:
    settings = _settings()
    settings.azure_openai_model = None

    with pytest.raises(azure_openai.AzureLLMConfigurationError, match="azure_openai_model"):
        azure_openai.generate_text("Question", settings)
