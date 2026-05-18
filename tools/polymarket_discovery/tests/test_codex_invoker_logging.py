# ruff: noqa: E402
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.providers.codex_invoker_logging import LoggingCodexInvoker
from polymarket_discovery.providers.llm_codex import CodexInvocationResult, CodexUsage

# ---------------------------------------------------------------------------
# Fake inner invoker
# ---------------------------------------------------------------------------

@dataclass
class _FakeInvoker:
    result: CodexInvocationResult

    def run(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        output_schema_path: Path | None = None,
    ) -> CodexInvocationResult:
        return self.result


# ---------------------------------------------------------------------------
# Helper: capture log records at INFO level
# ---------------------------------------------------------------------------

class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_logging_codex_invoker_returns_inner_result() -> None:
    """LoggingCodexInvoker.run() must return exactly what the inner invoker returns."""
    expected = CodexInvocationResult(text="hello", usage=None)
    inner = _FakeInvoker(result=expected)
    subject = LoggingCodexInvoker(inner=inner)

    actual = subject.run("prompt", timeout_seconds=10.0)

    assert actual is expected


def test_logging_codex_invoker_emits_codex_usage_when_usage_present() -> None:
    """When result.usage is not None, an INFO record named 'codex_usage' must be emitted."""
    usage = CodexUsage(
        input_tokens=100,
        cached_input_tokens=10,
        output_tokens=20,
        reasoning_output_tokens=5,
    )
    result = CodexInvocationResult(text="hello", usage=usage)
    inner = _FakeInvoker(result=result)
    subject = LoggingCodexInvoker(inner=inner)

    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    # Attach to the logger that LoggingCodexInvoker uses (__name__ inside its module)
    target_logger = logging.getLogger(
        "polymarket_discovery.providers.codex_invoker_logging"
    )
    target_logger.addHandler(handler)
    target_logger.setLevel(logging.INFO)

    try:
        subject.run("prompt", timeout_seconds=5.0)
    finally:
        target_logger.removeHandler(handler)

    usage_records = [r for r in handler.records if r.getMessage() == "codex_usage"]
    assert len(usage_records) == 1, f"Expected 1 codex_usage record, got {len(usage_records)}"

    record = usage_records[0]
    assert record.levelno == logging.INFO
    assert record.__dict__["input_tokens"] == 100
    assert record.__dict__["cached_input_tokens"] == 10
    assert record.__dict__["output_tokens"] == 20
    assert record.__dict__["reasoning_output_tokens"] == 5


def test_logging_codex_invoker_no_record_when_usage_none() -> None:
    """When result.usage is None, no codex_usage record must be emitted."""
    result = CodexInvocationResult(text="hello", usage=None)
    inner = _FakeInvoker(result=result)
    subject = LoggingCodexInvoker(inner=inner)

    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    target_logger = logging.getLogger(
        "polymarket_discovery.providers.codex_invoker_logging"
    )
    target_logger.addHandler(handler)
    target_logger.setLevel(logging.INFO)

    try:
        subject.run("prompt", timeout_seconds=5.0)
    finally:
        target_logger.removeHandler(handler)

    usage_records = [r for r in handler.records if r.getMessage() == "codex_usage"]
    assert len(usage_records) == 0, f"Expected no codex_usage records, got {len(usage_records)}"


def test_logging_codex_invoker_passes_schema_path() -> None:
    """output_schema_path must be forwarded to the inner invoker."""
    @dataclass
    class _CapturingInvoker:
        calls: list = field(default_factory=list)

        def run(self, prompt: str, *, timeout_seconds: float, output_schema_path: Path | None = None) -> CodexInvocationResult:
            self.calls.append(output_schema_path)
            return CodexInvocationResult(text="x", usage=None)

    inner = _CapturingInvoker()
    subject = LoggingCodexInvoker(inner=inner)
    schema = Path("/fake/schema.json")

    subject.run("p", timeout_seconds=1.0, output_schema_path=schema)

    assert inner.calls == [schema]
