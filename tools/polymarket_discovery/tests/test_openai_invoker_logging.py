from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.providers.openai_invoker import (  # noqa: E402
    OpenAIInvocationResult,
    OpenAIUsage,
)
from polymarket_discovery.providers.openai_invoker_logging import (  # noqa: E402
    LoggingOpenAIInvoker,
)


@dataclass
class _FakeInvoker:
    result: OpenAIInvocationResult

    def call(self, payload: dict[str, Any]) -> OpenAIInvocationResult:
        return self.result


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_logging_openai_invoker_returns_inner_result() -> None:
    expected = OpenAIInvocationResult(content="hello", usage=None)
    subject = LoggingOpenAIInvoker(inner=_FakeInvoker(result=expected))

    actual = subject.call({"model": "gpt-test", "messages": []})

    assert actual is expected


def test_logging_openai_invoker_emits_openai_usage_when_usage_present() -> None:
    usage = OpenAIUsage(prompt_tokens=120, completion_tokens=80, total_tokens=200)
    result = OpenAIInvocationResult(content="hello", usage=usage)
    subject = LoggingOpenAIInvoker(inner=_FakeInvoker(result=result))

    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    target_logger = logging.getLogger(
        "polymarket_discovery.providers.openai_invoker_logging"
    )
    target_logger.addHandler(handler)
    target_logger.setLevel(logging.INFO)

    try:
        subject.call({"model": "gpt-test", "messages": []})
    finally:
        target_logger.removeHandler(handler)

    usage_records = [r for r in handler.records if r.getMessage() == "openai_usage"]
    assert len(usage_records) == 1
    record = usage_records[0]
    assert record.levelno == logging.INFO
    assert record.__dict__["prompt_tokens"] == 120
    assert record.__dict__["completion_tokens"] == 80
    assert record.__dict__["total_tokens"] == 200


def test_logging_openai_invoker_no_record_when_usage_none() -> None:
    result = OpenAIInvocationResult(content="hello", usage=None)
    subject = LoggingOpenAIInvoker(inner=_FakeInvoker(result=result))

    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    target_logger = logging.getLogger(
        "polymarket_discovery.providers.openai_invoker_logging"
    )
    target_logger.addHandler(handler)
    target_logger.setLevel(logging.INFO)

    try:
        subject.call({"model": "gpt-test", "messages": []})
    finally:
        target_logger.removeHandler(handler)

    usage_records = [r for r in handler.records if r.getMessage() == "openai_usage"]
    assert len(usage_records) == 0
