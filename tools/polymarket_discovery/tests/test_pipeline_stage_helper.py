"""TDD tests for _run_stage helper in pipeline.py.

These tests must FAIL before the helper is implemented, then pass after.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.pipeline import _run_stage  # noqa: E402
from polymarket_discovery.utils.jsonl_logging import setup_jsonl_logging  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_stage_records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunStageEnabled:
    """When enabled=True the helper must call fn, return its result, and emit
    stage_started + stage_completed records."""

    def test_calls_fn_exactly_once(self, tmp_path: Path) -> None:
        fn = MagicMock(return_value="result_value")
        handler = setup_jsonl_logging(path=tmp_path / "s.jsonl", run_id="test-run")
        try:
            _run_stage("my_stage", enabled=True, default="default_value", fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        fn.assert_called_once_with()

    def test_returns_fn_result(self, tmp_path: Path) -> None:
        fn = MagicMock(return_value=42)
        handler = setup_jsonl_logging(path=tmp_path / "s.jsonl", run_id="test-run")
        try:
            result = _run_stage("my_stage", enabled=True, default=0, fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        assert result == 42

    def test_emits_stage_started_and_completed(self, tmp_path: Path) -> None:
        log_path = tmp_path / "s.jsonl"
        handler = setup_jsonl_logging(path=log_path, run_id="test-run")
        fn = MagicMock(return_value=None)
        try:
            _run_stage("my_stage", enabled=True, default=None, fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        records = _read_stage_records(log_path)
        events = [(r["event"], r.get("stage")) for r in records]
        assert events == [
            ("stage_started", "my_stage"),
            ("stage_completed", "my_stage"),
        ]


class TestRunStageDisabled:
    """When enabled=False the helper must NOT call fn, return default, and emit
    a stage_skipped record."""

    def test_does_not_call_fn(self, tmp_path: Path) -> None:
        fn = MagicMock()
        handler = setup_jsonl_logging(path=tmp_path / "s.jsonl", run_id="test-run")
        try:
            _run_stage("my_stage", enabled=False, default="sentinel", fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        fn.assert_not_called()

    def test_returns_default(self, tmp_path: Path) -> None:
        fn = MagicMock()
        handler = setup_jsonl_logging(path=tmp_path / "s.jsonl", run_id="test-run")
        try:
            result = _run_stage("my_stage", enabled=False, default="sentinel", fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        assert result == "sentinel"

    def test_emits_stage_skipped_record(self, tmp_path: Path) -> None:
        log_path = tmp_path / "s.jsonl"
        handler = setup_jsonl_logging(path=log_path, run_id="test-run")
        fn = MagicMock()
        try:
            _run_stage("my_stage", enabled=False, default=None, fn=fn)
        finally:
            logging.getLogger("polymarket_discovery").removeHandler(handler)
            handler.close()
        records = _read_stage_records(log_path)
        assert len(records) == 1
        assert records[0]["event"] == "stage_skipped"
        assert records[0]["stage"] == "my_stage"
        assert records[0]["reason"] == "disabled_in_config"
