from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.providers.openai_invoker import (  # noqa: E402
    OpenAIInvocationResult,
    OpenAIUsage,
    RequestJsonOpenAIInvoker,
)
from polymarket_discovery.providers.settings import LLMProviderSettings  # noqa: E402


def _settings(api_key: str = "test-key") -> LLMProviderSettings:
    return LLMProviderSettings(
        provider_name="openai-compatible",
        model_name="gpt-test",
        base_url="https://api.example.com/v1/chat/completions",
        api_key=api_key,
    )


def _fake_response(content: str = "hello", usage: dict[str, int] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "choices": [{"message": {"content": content}}],
    }
    if usage is not None:
        payload["usage"] = usage
    return payload


def test_call_returns_invocation_result_with_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polymarket_discovery.providers.openai_invoker.request_json",
        lambda **kwargs: _fake_response(content="answer-text"),
    )
    invoker = RequestJsonOpenAIInvoker(settings=_settings())

    result = invoker.call({"model": "gpt-test", "messages": []})

    assert isinstance(result, OpenAIInvocationResult)
    assert result.content == "answer-text"


def test_call_populates_usage_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polymarket_discovery.providers.openai_invoker.request_json",
        lambda **kwargs: _fake_response(
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        ),
    )
    invoker = RequestJsonOpenAIInvoker(settings=_settings())

    result = invoker.call({"model": "gpt-test", "messages": []})

    assert isinstance(result.usage, OpenAIUsage)
    assert result.usage.prompt_tokens == 100
    assert result.usage.completion_tokens == 50
    assert result.usage.total_tokens == 150


def test_call_returns_none_usage_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polymarket_discovery.providers.openai_invoker.request_json",
        lambda **kwargs: _fake_response(usage=None),
    )
    invoker = RequestJsonOpenAIInvoker(settings=_settings())

    result = invoker.call({"model": "gpt-test", "messages": []})

    assert result.usage is None


def test_call_raises_on_missing_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polymarket_discovery.providers.openai_invoker.request_json",
        lambda **kwargs: {"choices": [{"message": {"content": ""}}]},
    )
    invoker = RequestJsonOpenAIInvoker(settings=_settings())

    with pytest.raises(ValueError, match="non-empty string content"):
        invoker.call({"model": "gpt-test", "messages": []})


def test_call_passes_payload_and_auth_to_request_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _fake_response()

    monkeypatch.setattr(
        "polymarket_discovery.providers.openai_invoker.request_json",
        fake_request_json,
    )
    invoker = RequestJsonOpenAIInvoker(settings=_settings(api_key="secret-key"))

    invoker.call({"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]})

    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["method"] == "POST"
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
