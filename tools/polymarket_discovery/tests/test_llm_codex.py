from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.providers.factories import build_llm_provider
from polymarket_discovery.providers.llm_codex import (
    CodexCliLLMProvider,
    SubprocessCodexInvoker,
    _extract_json_object,
)
from polymarket_discovery.providers.settings import (
    LLMProviderSettings,
    resolve_llm_settings,
)


@dataclass
class _FakeInvoker:
    response: str = ""
    error: Exception | None = None
    calls: list[tuple[str, float]] = field(default_factory=list)

    def run(self, prompt: str, *, timeout_seconds: float) -> str:
        self.calls.append((prompt, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.response


def _market(market_id: str, question: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=question,
        description="desc",
        rules="rules",
        end_date="2026-11-03",
        topic="election",
        token_ids=[f"tok-{market_id}"],
    )


def _settings(**overrides: object) -> LLMProviderSettings:
    base = dict(
        provider_name="codex",
        model_name="gpt-5.4",
        base_url="",
        api_key="",
        timeout_seconds=30.0,
        temperature=0.0,
        max_tokens=256,
    )
    base.update(overrides)
    return LLMProviderSettings(**base)  # type: ignore[arg-type]


def test_extract_json_object_returns_clean_json_unchanged() -> None:
    raw = '{"edge_type":"related","confidence":0.5,"rationale":"x"}'
    assert _extract_json_object(raw) == raw


def test_extract_json_object_strips_surrounding_whitespace() -> None:
    raw = '\n\n  {"edge_type":"related","confidence":0.5,"rationale":"x"}  \n'
    assert _extract_json_object(raw) == '{"edge_type":"related","confidence":0.5,"rationale":"x"}'


def test_extract_json_object_strips_fenced_code_block() -> None:
    raw = '```json\n{"edge_type":"related","confidence":0.5,"rationale":"x"}\n```'
    assert _extract_json_object(raw) == '{"edge_type":"related","confidence":0.5,"rationale":"x"}'


def test_extract_json_object_strips_unlabelled_fenced_block() -> None:
    raw = '```\n{"edge_type":"related","confidence":0.5,"rationale":"x"}\n```'
    assert _extract_json_object(raw) == '{"edge_type":"related","confidence":0.5,"rationale":"x"}'


def test_extract_json_object_recovers_object_wrapped_in_prose() -> None:
    raw = (
        "Sure, here is my analysis:\n"
        '{"edge_type":"conditional","confidence":0.7,"rationale":"shared resolution"}'
        "\nLet me know if you need more."
    )
    assert (
        _extract_json_object(raw)
        == '{"edge_type":"conditional","confidence":0.7,"rationale":"shared resolution"}'
    )


def test_extract_json_object_handles_nested_braces() -> None:
    raw = 'preamble {"edge_type":"related","confidence":0.5,"rationale":"a {b} c"} trailer'
    assert (
        _extract_json_object(raw)
        == '{"edge_type":"related","confidence":0.5,"rationale":"a {b} c"}'
    )


def test_extract_json_object_returns_first_object_when_multiple_present() -> None:
    raw = (
        '{"edge_type":"related","confidence":0.5,"rationale":"first"}'
        ' and then '
        '{"edge_type":"conditional","confidence":0.9,"rationale":"second"}'
    )
    assert (
        _extract_json_object(raw)
        == '{"edge_type":"related","confidence":0.5,"rationale":"first"}'
    )


def test_extract_json_object_raises_when_no_object_present() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _extract_json_object("Sorry, I cannot help with that request.")


def test_extract_json_object_raises_on_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        _extract_json_object("")


def test_extract_json_object_raises_when_braces_unbalanced() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _extract_json_object('{"edge_type":"related","confidence":0.5')


def test_codex_provider_returns_validated_prediction_for_clean_json() -> None:
    invoker = _FakeInvoker(
        response='{"edge_type":"conditional","confidence":0.7,"rationale":"shared resolution"}'
    )
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    prediction = provider.infer_dependency(
        _market("m1", "Will A win?"),
        _market("m2", "Will B win?"),
    )

    assert prediction.edge_type == "conditional"
    assert prediction.confidence == pytest.approx(0.7)
    assert prediction.rationale == "shared resolution"


def test_codex_provider_passes_settings_timeout_to_invoker() -> None:
    invoker = _FakeInvoker(
        response='{"edge_type":"related","confidence":0.5,"rationale":"x"}'
    )
    provider = CodexCliLLMProvider(settings=_settings(timeout_seconds=42.0), invoker=invoker)

    provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))

    assert len(invoker.calls) == 1
    _, timeout = invoker.calls[0]
    assert timeout == 42.0


def test_codex_provider_prompt_contains_both_market_questions() -> None:
    invoker = _FakeInvoker(
        response='{"edge_type":"related","confidence":0.5,"rationale":"x"}'
    )
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    provider.infer_dependency(
        _market("m1", "Will Candidate A win?"),
        _market("m2", "Will Candidate B win?"),
    )

    prompt, _ = invoker.calls[0]
    assert "Will Candidate A win?" in prompt
    assert "Will Candidate B win?" in prompt
    assert "edge_type" in prompt
    assert "mutually_exclusive" in prompt


def test_codex_provider_recovers_from_fenced_response() -> None:
    invoker = _FakeInvoker(
        response='```json\n{"edge_type":"related","confidence":0.5,"rationale":"x"}\n```'
    )
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    prediction = provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))

    assert prediction.edge_type == "related"


def test_codex_provider_recovers_from_prose_wrapped_response() -> None:
    invoker = _FakeInvoker(
        response=(
            "Here is the analysis:\n"
            '{"edge_type":"mutually_exclusive","confidence":0.95,"rationale":"only one wins"}'
            "\nThanks."
        )
    )
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    prediction = provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))

    assert prediction.edge_type == "mutually_exclusive"
    assert prediction.confidence == pytest.approx(0.95)


def test_codex_provider_propagates_invoker_error() -> None:
    invoker = _FakeInvoker(error=RuntimeError("codex exited 1: not authenticated"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(RuntimeError, match="not authenticated"):
        provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))


def test_codex_provider_rejects_invalid_edge_type() -> None:
    invoker = _FakeInvoker(
        response='{"edge_type":"basket","confidence":0.5,"rationale":"x"}'
    )
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="edge_type"):
        provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))


def test_codex_provider_rejects_empty_response() -> None:
    invoker = _FakeInvoker(response="")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="empty"):
        provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))


def test_codex_provider_rejects_non_json_response() -> None:
    invoker = _FakeInvoker(response="I cannot help with that.")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="JSON object"):
        provider.infer_dependency(_market("m1", "L?"), _market("m2", "R?"))


def test_subprocess_invoker_returns_stdout_from_binary() -> None:
    invoker = SubprocessCodexInvoker(binary="cat", base_args=(), use_json_flag=False)

    result = invoker.run("hello world", timeout_seconds=5.0)

    assert result == "hello world"


def test_subprocess_invoker_passes_base_args_and_json_flag() -> None:
    # `printf '%s\n' --json --extra` echoes its args; we use it to prove the
    # invoker constructs argv as: [binary, *base_args, "--json"] and feeds
    # the prompt on stdin (printf ignores stdin).
    invoker = SubprocessCodexInvoker(
        binary="printf",
        base_args=("%s\n", "--extra"),
        use_json_flag=True,
    )

    result = invoker.run("ignored stdin", timeout_seconds=5.0)

    assert result.splitlines() == ["--extra", "--json"]


def test_subprocess_invoker_raises_when_binary_exits_nonzero() -> None:
    invoker = SubprocessCodexInvoker(binary="false", base_args=(), use_json_flag=False)

    with pytest.raises(RuntimeError, match="exited"):
        invoker.run("anything", timeout_seconds=5.0)


def test_subprocess_invoker_raises_when_binary_missing() -> None:
    invoker = SubprocessCodexInvoker(
        binary="/nonexistent/codex-binary-xyz",
        base_args=(),
        use_json_flag=False,
    )

    with pytest.raises(RuntimeError, match="codex"):
        invoker.run("anything", timeout_seconds=5.0)


def _config(tmp_path: Path, **params: object) -> DiscoveryConfig:
    return DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="codex-passthrough",
        params=dict(params),
    )


@pytest.mark.parametrize("name", ["codex", "codex_cli", "codex-cli"])
def test_resolve_llm_settings_recognizes_codex_provider_aliases(
    tmp_path: Path,
    name: str,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "llm_provider": name,
            "model": "gpt-5.4",
            "timeout_seconds": 60,
        },
    )

    settings = resolve_llm_settings(config)

    assert settings.provider_name == "codex"
    assert settings.model_name == "gpt-5.4"
    assert settings.timeout_seconds == 60


def test_resolve_llm_settings_codex_does_not_require_base_url_or_api_key(
    tmp_path: Path,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={"llm_provider": "codex"},
    )

    settings = resolve_llm_settings(config)

    assert settings.base_url == ""
    assert settings.api_key == ""


def test_build_llm_provider_returns_codex_adapter(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "llm_provider": "codex",
            "model": "gpt-5.4",
        },
    )

    provider = build_llm_provider(config)

    assert isinstance(provider, CodexCliLLMProvider)
    assert provider.settings.model_name == "gpt-5.4"
    assert isinstance(provider.invoker, SubprocessCodexInvoker)


def test_build_llm_provider_codex_supports_invoker_overrides(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "llm_provider": "codex",
            "codex_binary": "/usr/local/bin/codex-custom",
            "codex_args": ["chat", "--model", "gpt-5.4"],
            "codex_use_json_flag": False,
        },
    )

    provider = build_llm_provider(config)

    assert isinstance(provider, CodexCliLLMProvider)
    assert isinstance(provider.invoker, SubprocessCodexInvoker)
    assert provider.invoker.binary == "/usr/local/bin/codex-custom"
    assert provider.invoker.base_args == ("chat", "--model", "gpt-5.4")
    assert provider.invoker.use_json_flag is False


def test_subprocess_invoker_raises_on_timeout() -> None:
    invoker = SubprocessCodexInvoker(
        binary="sleep",
        base_args=("5",),
        use_json_flag=False,
    )

    with pytest.raises(RuntimeError, match="timed out"):
        invoker.run("ignored", timeout_seconds=0.2)
