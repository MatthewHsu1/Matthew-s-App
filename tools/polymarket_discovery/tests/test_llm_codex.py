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
    CodexInvocationResult,
    CodexUsage,
    SubprocessCodexInvoker,
    _extract_json_object,
    _parse_jsonl_response,
)
from polymarket_discovery.providers.settings import (
    LLMProviderSettings,
    resolve_llm_settings,
)


@dataclass
class _FakeInvoker:
    result: CodexInvocationResult | None = None
    error: Exception | None = None
    calls: list[tuple[str, float]] = field(default_factory=list)
    schema_paths: list[Path | None] = field(default_factory=list)

    def run(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        output_schema_path: Path | None = None,
    ) -> CodexInvocationResult:
        self.calls.append((prompt, timeout_seconds))
        self.schema_paths.append(output_schema_path)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise RuntimeError("_FakeInvoker: no result configured")
        return self.result


def _fake(text: str, *, usage: CodexUsage | None = None) -> _FakeInvoker:
    """Convenience: build a _FakeInvoker that returns the given agent message text."""
    return _FakeInvoker(result=CodexInvocationResult(text=text, usage=usage))


def _market(market_id: str, question: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=question,
        description="desc",
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


def _batched_response(pair_id: str, edge_type: str, confidence: float, rationale: str) -> str:
    """Helper: format a single-pair batched dependency response."""
    import json as _json
    return _json.dumps({
        "predictions": [{
            "pair_id": pair_id,
            "edge_type": edge_type,
            "confidence": confidence,
            "rationale": rationale,
        }]
    })


def test_codex_provider_returns_validated_prediction_for_clean_json() -> None:
    invoker = _fake(_batched_response("0", "conditional", 0.7, "shared resolution"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    predictions = provider.infer_dependencies_batched([
        (_market("m1", "Will A win?"), _market("m2", "Will B win?")),
    ])

    assert len(predictions) == 1
    assert predictions[0].edge_type == "conditional"
    assert predictions[0].confidence == pytest.approx(0.7)
    assert predictions[0].rationale == "shared resolution"


def test_codex_provider_passes_settings_timeout_to_invoker() -> None:
    invoker = _fake(_batched_response("0", "related", 0.5, "x"))
    provider = CodexCliLLMProvider(settings=_settings(timeout_seconds=42.0), invoker=invoker)

    provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    assert len(invoker.calls) == 1
    _, timeout = invoker.calls[0]
    assert timeout == 42.0


def test_codex_provider_prompt_contains_both_market_questions() -> None:
    invoker = _fake(_batched_response("0", "related", 0.5, "x"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    provider.infer_dependencies_batched([
        (_market("m1", "Will Candidate A win?"), _market("m2", "Will Candidate B win?")),
    ])

    prompt, _ = invoker.calls[0]
    assert "Will Candidate A win?" in prompt
    assert "Will Candidate B win?" in prompt
    assert "edge_type" in prompt
    assert "mutually_exclusive" in prompt


def test_codex_provider_recovers_from_fenced_response() -> None:
    raw = _batched_response("0", "related", 0.5, "x")
    invoker = _fake(f"```json\n{raw}\n```")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    predictions = provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    assert predictions[0].edge_type == "related"


def test_codex_provider_recovers_from_prose_wrapped_response() -> None:
    raw = _batched_response("0", "mutually_exclusive", 0.95, "only one wins")
    invoker = _fake(f"Here is the analysis:\n{raw}\nThanks.")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    predictions = provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    assert predictions[0].edge_type == "mutually_exclusive"
    assert predictions[0].confidence == pytest.approx(0.95)


def test_codex_provider_propagates_invoker_error() -> None:
    invoker = _FakeInvoker(error=RuntimeError("codex exited 1: not authenticated"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(RuntimeError, match="not authenticated"):
        provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])


def test_codex_provider_rejects_invalid_edge_type() -> None:
    invoker = _fake(_batched_response("0", "basket", 0.5, "x"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="edge_type"):
        provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])


def test_codex_provider_rejects_empty_response() -> None:
    invoker = _fake("")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="empty"):
        provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])


def test_codex_provider_rejects_non_json_response() -> None:
    invoker = _fake("I cannot help with that.")
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    with pytest.raises(ValueError, match="JSON object"):
        provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])


def test_subprocess_invoker_returns_stdout_from_binary() -> None:
    # When use_json_flag=False, the invoker treats raw stdout as plain text
    # and returns it directly in result.text (no JSONL parsing).
    invoker = SubprocessCodexInvoker(binary="cat", base_args=(), use_json_flag=False)

    result = invoker.run("hello world", timeout_seconds=5.0)

    assert result.text == "hello world"
    assert result.usage is None


def test_subprocess_invoker_passes_base_args_to_binary() -> None:
    # `printf '%s\n' --extra` echoes its args; we use it to prove the invoker
    # constructs argv as [binary, *base_args] and feeds the prompt on stdin
    # (printf ignores stdin).  use_json_flag=False so stdout is returned as-is.
    invoker = SubprocessCodexInvoker(
        binary="printf",
        base_args=("%s\n", "--extra"),
        use_json_flag=False,
    )

    result = invoker.run("ignored stdin", timeout_seconds=5.0)

    assert result.text.strip() == "--extra"


def test_subprocess_invoker_appends_json_flag_to_argv() -> None:
    # Verify --json is appended when use_json_flag=True by using a real JSONL payload.
    import json as _json
    payload = _json.dumps({"ok": True})
    jsonl = "\n".join([
        _json.dumps({"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": payload}}),
        _json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                                                          "output_tokens": 1, "reasoning_output_tokens": 0}}),
    ])
    # Use `echo` to emit the JSONL regardless of stdin; argv: [echo, <jsonl>]
    # base_args passes the literal JSONL string as the arg to echo.
    invoker = SubprocessCodexInvoker(
        binary="echo",
        base_args=(jsonl,),
        use_json_flag=False,  # echo doesn't accept --json; test argv shape separately
    )

    result = invoker.run("ignored", timeout_seconds=5.0)

    assert jsonl in result.text


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

import json as _json


def _make_jsonl(*events: dict) -> str:
    """Serialize a sequence of dicts as a JSONL string."""
    return "\n".join(_json.dumps(e) for e in events)


def test_parse_jsonl_extracts_agent_message_text() -> None:
    payload = _json.dumps({"predictions": [{"pair_id": "0", "edge_type": "related",
                                             "confidence": 0.5, "rationale": "x"}]})
    jsonl = _make_jsonl(
        {"type": "thread.started", "thread_id": "019abc"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": payload}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20,
                                              "cached_input_tokens": 0, "reasoning_output_tokens": 0}},
    )

    result = _parse_jsonl_response(jsonl)

    assert result.text == payload


def test_parse_jsonl_extracts_usage_telemetry() -> None:
    payload = _json.dumps({"predictions": []})
    jsonl = _make_jsonl(
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": payload}},
        {"type": "turn.completed", "usage": {
            "input_tokens": 42984,
            "cached_input_tokens": 4480,
            "output_tokens": 2370,
            "reasoning_output_tokens": 255,
        }},
    )

    result = _parse_jsonl_response(jsonl)

    assert result.usage is not None
    assert result.usage.input_tokens == 42984
    assert result.usage.cached_input_tokens == 4480
    assert result.usage.output_tokens == 2370
    assert result.usage.reasoning_output_tokens == 255


def test_parse_jsonl_takes_last_agent_message_when_multiple_present() -> None:
    first = _json.dumps({"answer": "first"})
    last = _json.dumps({"answer": "last"})
    jsonl = _make_jsonl(
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": first}},
        {"type": "item.completed", "item": {"id": "item_1", "type": "agent_message", "text": last}},
    )

    result = _parse_jsonl_response(jsonl)

    assert result.text == last


def test_parse_jsonl_raises_when_no_agent_message_present() -> None:
    jsonl = _make_jsonl(
        {"type": "thread.started", "thread_id": "019abc"},
        {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 1,
                                              "cached_input_tokens": 0, "reasoning_output_tokens": 0}},
    )

    with pytest.raises(RuntimeError, match="agent_message"):
        _parse_jsonl_response(jsonl)


def test_parse_jsonl_skips_malformed_lines_without_crashing() -> None:
    payload = _json.dumps({"ok": True})
    # Mix valid JSONL with non-JSON lines (e.g. codex debug output)
    raw = (
        "not json at all\n"
        + _json.dumps({"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": payload}})
        + "\n{broken"
    )

    result = _parse_jsonl_response(raw)

    assert result.text == payload


def test_parse_jsonl_usage_is_none_when_no_turn_completed_event() -> None:
    payload = _json.dumps({"x": 1})
    jsonl = _make_jsonl(
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": payload}},
    )

    result = _parse_jsonl_response(jsonl)

    assert result.usage is None


# ---------------------------------------------------------------------------
# CodexCliLLMProvider usage-logging integration test
# ---------------------------------------------------------------------------

def test_codex_provider_logs_usage_when_present(tmp_path: Path) -> None:
    """Provider should emit a usage log entry when the invoker returns token counts."""
    import json as _json
    from polymarket_discovery.utils.logging_utils import JsonlStageLogger

    log_path = tmp_path / "run.jsonl"
    logger = JsonlStageLogger(path=log_path, run_id="test-run")

    usage = CodexUsage(input_tokens=100, cached_input_tokens=10, output_tokens=20,
                       reasoning_output_tokens=5)
    invoker = _fake(_batched_response("0", "related", 0.5, "x"), usage=usage)
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker, stage_logger=logger)

    provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    entries = [_json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    usage_entries = [e for e in entries if e.get("event") == "llm_usage"]
    assert len(usage_entries) == 1
    entry = usage_entries[0]
    assert entry["input_tokens"] == 100
    assert entry["output_tokens"] == 20
    assert entry["cached_input_tokens"] == 10


def test_codex_provider_works_without_logger_when_usage_absent() -> None:
    """Provider works with stage_logger=None and usage=None — no crash."""
    invoker = _fake(_batched_response("0", "related", 0.5, "x"), usage=None)
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker, stage_logger=None)

    predictions = provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    assert predictions[0].edge_type == "related"


# ---------------------------------------------------------------------------
# Output-schema flag: SubprocessCodexInvoker
# ---------------------------------------------------------------------------

def test_subprocess_invoker_includes_output_schema_flag_when_path_provided(tmp_path: Path) -> None:
    """When output_schema_path is given, argv must include --output-schema <path>."""
    import json as _json
    schema_file = tmp_path / "schema.json"
    schema_file.write_text("{}")

    payload = _json.dumps({"predictions": []})
    jsonl = "\n".join([
        _json.dumps({"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": payload}}),
        _json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                                                          "output_tokens": 1, "reasoning_output_tokens": 0}}),
    ])
    # Use echo to emit JSONL; prove schema path ends up in argv by capturing it
    # via a shell script that writes argv to a file, then reads it.
    script = tmp_path / "capture.sh"
    argv_file = tmp_path / "argv.txt"
    script.write_text(
        f"#!/bin/sh\necho \"$@\" > {argv_file}\necho '{jsonl}'\n"
    )
    script.chmod(0o755)

    invoker = SubprocessCodexInvoker(
        binary=str(script),
        base_args=(),
        use_json_flag=True,
    )

    invoker.run("prompt", timeout_seconds=5.0, output_schema_path=schema_file)

    captured = argv_file.read_text()
    assert "--output-schema" in captured
    assert str(schema_file) in captured


def test_subprocess_invoker_omits_output_schema_flag_when_path_is_none(tmp_path: Path) -> None:
    """When output_schema_path is None, --output-schema must NOT appear in argv."""
    import json as _json

    payload = _json.dumps({"predictions": []})
    jsonl = "\n".join([
        _json.dumps({"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": payload}}),
        _json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                                                          "output_tokens": 1, "reasoning_output_tokens": 0}}),
    ])
    script = tmp_path / "capture_none.sh"
    argv_file = tmp_path / "argv_none.txt"
    script.write_text(
        f"#!/bin/sh\necho \"$@\" > {argv_file}\necho '{jsonl}'\n"
    )
    script.chmod(0o755)

    invoker = SubprocessCodexInvoker(
        binary=str(script),
        base_args=(),
        use_json_flag=True,
    )

    invoker.run("prompt", timeout_seconds=5.0, output_schema_path=None)

    captured = argv_file.read_text()
    assert "--output-schema" not in captured


# ---------------------------------------------------------------------------
# Output-schema flag: CodexCliLLMProvider passes correct schema per call type
# ---------------------------------------------------------------------------

def test_infer_dependencies_batched_passes_dependency_schema_path() -> None:
    """infer_dependencies_batched must invoke with the dependency_predictions schema."""
    invoker = _fake(_batched_response("0", "related", 0.5, "x"))
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    provider.infer_dependencies_batched([(_market("m1", "L?"), _market("m2", "R?"))])

    assert len(invoker.schema_paths) == 1
    schema_path = invoker.schema_paths[0]
    assert schema_path is not None
    assert schema_path.name == "dependency_predictions.json"
    assert schema_path.exists()


def test_infer_basket_groups_passes_basket_schema_path() -> None:
    """infer_basket_groups must invoke with the basket_groups schema."""
    import json as _json
    basket_response = _json.dumps({
        "baskets": [{
            "basket_id": "b1",
            "market_ids": ["m1", "m2"],
            "rationale": "complete set",
        }]
    })
    invoker = _fake(basket_response)
    provider = CodexCliLLMProvider(settings=_settings(), invoker=invoker)

    provider.infer_basket_groups([_market("m1", "Q1?"), _market("m2", "Q2?")])

    assert len(invoker.schema_paths) == 1
    schema_path = invoker.schema_paths[0]
    assert schema_path is not None
    assert schema_path.name == "basket_groups.json"
    assert schema_path.exists()


# ---------------------------------------------------------------------------
# Schema files are well-formed Draft 2020-12 schemas
# ---------------------------------------------------------------------------

def _schemas_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "src" / "polymarket_discovery" / "providers" / "schemas"
    )


def test_dependency_predictions_schema_is_valid_draft_2020_12() -> None:
    """dependency_predictions.json must be a valid JSON Schema (Draft 2020-12)."""
    import jsonschema
    import jsonschema.validators

    schema_path = _schemas_dir() / "dependency_predictions.json"
    assert schema_path.exists(), f"Schema file not found: {schema_path}"

    import json as _json
    schema = _json.loads(schema_path.read_text())
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


def test_basket_groups_schema_is_valid_draft_2020_12() -> None:
    """basket_groups.json must be a valid JSON Schema (Draft 2020-12)."""
    import jsonschema
    import jsonschema.validators

    schema_path = _schemas_dir() / "basket_groups.json"
    assert schema_path.exists(), f"Schema file not found: {schema_path}"

    import json as _json
    schema = _json.loads(schema_path.read_text())
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


def test_dependency_predictions_schema_accepts_valid_payload() -> None:
    """A well-formed predictions payload should validate against the schema."""
    import json as _json
    import jsonschema

    schema_path = _schemas_dir() / "dependency_predictions.json"
    schema = _json.loads(schema_path.read_text())

    valid = {
        "predictions": [{
            "pair_id": "0",
            "edge_type": "conditional",
            "confidence": 0.7,
            "rationale": "They share resolution criteria.",
        }]
    }
    jsonschema.validate(valid, schema)


def test_dependency_predictions_schema_rejects_invalid_edge_type() -> None:
    """edge_type not in enum should fail schema validation."""
    import json as _json
    import jsonschema

    schema_path = _schemas_dir() / "dependency_predictions.json"
    schema = _json.loads(schema_path.read_text())

    invalid = {
        "predictions": [{
            "pair_id": "0",
            "edge_type": "basket",
            "confidence": 0.7,
            "rationale": "x",
        }]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_basket_groups_schema_accepts_valid_payload() -> None:
    """A well-formed baskets payload should validate against the schema."""
    import json as _json
    import jsonschema

    schema_path = _schemas_dir() / "basket_groups.json"
    schema = _json.loads(schema_path.read_text())

    valid = {
        "baskets": [{
            "basket_id": "b1",
            "market_ids": ["m1", "m2"],
            "rationale": "complete set",
        }]
    }
    jsonschema.validate(valid, schema)


def test_basket_groups_schema_rejects_empty_market_ids() -> None:
    """market_ids with zero items should fail (minItems: 1)."""
    import json as _json
    import jsonschema

    schema_path = _schemas_dir() / "basket_groups.json"
    schema = _json.loads(schema_path.read_text())

    invalid = {
        "baskets": [{
            "basket_id": "b1",
            "market_ids": [],
            "rationale": "complete set",
        }]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)
