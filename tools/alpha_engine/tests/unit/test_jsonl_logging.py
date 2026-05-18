from __future__ import annotations

import json
import logging
from pathlib import Path

from alpha_engine.logging_.jsonl import (
    PACKAGE_LOGGER_NAME,
    setup_jsonl_logging,
)


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_setup_writes_jsonl_with_run_id(tmp_path):
    log_path = tmp_path / "engine.jsonl"
    handler = setup_jsonl_logging(
        path=log_path, run_id="run_123", env_name="toy", mode="backtest"
    )
    try:
        logging.getLogger(PACKAGE_LOGGER_NAME).info(
            "engine_started", extra={"strategy": "toy_buy_and_hold"}
        )
        handler.flush()
        lines = _read_lines(log_path)
        assert len(lines) == 1
        line = lines[0]
        assert line["event"] == "engine_started"
        assert line["run_id"] == "run_123"
        assert line["env_name"] == "toy"
        assert line["mode"] == "backtest"
        assert line["strategy"] == "toy_buy_and_hold"
        assert "ts" in line
    finally:
        logging.getLogger(PACKAGE_LOGGER_NAME).removeHandler(handler)


def test_event_constants_exist():
    from alpha_engine.logging_.events import (
        ENGINE_STARTED,
        ORDER_FILLED,
        RISK_CHECK,
    )
    assert ENGINE_STARTED == "engine_started"
    assert ORDER_FILLED == "order_filled"
    assert RISK_CHECK == "risk_check"
