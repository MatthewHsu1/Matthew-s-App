from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from polymarket_discovery.utils.jsonl_logging import (
    JsonlHandler,
    RunIdFilter,
    setup_jsonl_logging,
    stage,
)


def _make_record(msg: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_jsonl_handler_writes_one_json_per_record(tmp_path: Path) -> None:
    log_path = tmp_path / "stages.jsonl"
    handler = JsonlHandler(path=log_path)

    handler.handle(_make_record("hello_event"))
    handler.close()

    records = _read_jsonl(log_path)
    assert len(records) == 1
    assert records[0]["event"] == "hello_event"
    assert "ts" in records[0]


def test_jsonl_handler_includes_extra_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "stages.jsonl"
    handler = JsonlHandler(path=log_path)

    handler.handle(_make_record("stage_completed", stage="market_source", duration_ms=42))
    handler.close()

    rec = _read_jsonl(log_path)[0]
    assert rec["event"] == "stage_completed"
    assert rec["stage"] == "market_source"
    assert rec["duration_ms"] == 42


def test_run_id_filter_injects_run_id(tmp_path: Path) -> None:
    log_path = tmp_path / "stages.jsonl"
    handler = JsonlHandler(path=log_path)
    handler.addFilter(RunIdFilter(run_id="run_xyz"))

    handler.handle(_make_record("started"))
    handler.close()

    rec = _read_jsonl(log_path)[0]
    assert rec["run_id"] == "run_xyz"


@pytest.fixture()
def package_logger(tmp_path: Path):
    log_path = tmp_path / "stages.jsonl"
    handler = JsonlHandler(path=log_path)
    logger = logging.getLogger("polymarket_discovery")
    prior_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield log_path
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prior_level)
        handler.close()


def test_stage_emits_started_then_completed(package_logger: Path) -> None:
    with stage("market_source"):
        pass

    records = _read_jsonl(package_logger)
    assert [r["event"] for r in records] == ["stage_started", "stage_completed"]
    assert all(r["stage"] == "market_source" for r in records)
    assert isinstance(records[1]["duration_ms"], int)
    assert records[1]["duration_ms"] >= 0


def test_setup_jsonl_logging_attaches_handler_and_stamps_run_id(tmp_path: Path) -> None:
    log_path = tmp_path / "stages.jsonl"
    pkg_logger = logging.getLogger("polymarket_discovery")
    prior_handlers = list(pkg_logger.handlers)
    prior_level = pkg_logger.level

    handler = setup_jsonl_logging(path=log_path, run_id="run_abc")
    try:
        with stage("market_source"):
            pass
        logging.getLogger("polymarket_discovery.some.child").info(
            "custom_event", extra={"foo": 1}
        )
    finally:
        pkg_logger.removeHandler(handler)
        pkg_logger.handlers = prior_handlers
        pkg_logger.setLevel(prior_level)
        handler.close()

    records = _read_jsonl(log_path)
    events = [r["event"] for r in records]
    assert "stage_started" in events
    assert "stage_completed" in events
    assert "custom_event" in events
    assert all(r["run_id"] == "run_abc" for r in records)
    custom = next(r for r in records if r["event"] == "custom_event")
    assert custom["foo"] == 1


def test_stage_emits_failed_and_reraises(package_logger: Path) -> None:
    with pytest.raises(ValueError, match="boom"):
        with stage("topic_assigner"):
            raise ValueError("boom")

    records = _read_jsonl(package_logger)
    assert [r["event"] for r in records] == ["stage_started", "stage_failed"]
    failed = records[1]
    assert failed["stage"] == "topic_assigner"
    assert failed["error_type"] == "ValueError"
    assert failed["error"] == "boom"
    assert isinstance(failed["duration_ms"], int)
