from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_engine.control.last_run import LastRunWriter, read_last_run


def test_write_creates_file_with_required_fields(tmp_path: Path):
    path = tmp_path / "last_run.json"
    w = LastRunWriter(path)
    w.write(
        pid=12345,
        started_ts=datetime(2026, 5, 16, 14, 23, 1, tzinfo=timezone.utc),
        mode="paper",
        run_id="2026-05-16T142301Z-abc",
        env_name="ibkr_paper_aapl",
    )
    data = json.loads(path.read_text())
    assert data["pid"] == 12345
    assert data["mode"] == "paper"
    assert data["env_name"] == "ibkr_paper_aapl"
    assert data["run_id"] == "2026-05-16T142301Z-abc"
    assert "heartbeat_ts" in data
    assert "started_ts" in data


def test_heartbeat_updates_only_heartbeat(tmp_path: Path):
    path = tmp_path / "last_run.json"
    w = LastRunWriter(path)
    w.write(
        pid=1,
        started_ts=datetime(2026, 5, 16, tzinfo=timezone.utc),
        mode="paper",
        run_id="r1",
        env_name="e",
    )
    initial = json.loads(path.read_text())
    w.heartbeat(datetime(2026, 5, 16, 15, tzinfo=timezone.utc))
    updated = json.loads(path.read_text())
    assert updated["pid"] == initial["pid"]
    assert updated["run_id"] == initial["run_id"]
    assert updated["heartbeat_ts"] != initial["heartbeat_ts"]


def test_read_last_run_round_trips(tmp_path: Path):
    path = tmp_path / "last_run.json"
    w = LastRunWriter(path)
    w.write(
        pid=99,
        started_ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mode="paper",
        run_id="r",
        env_name="env_a",
    )
    data = read_last_run(path)
    assert data["pid"] == 99
    assert data["env_name"] == "env_a"


def test_read_last_run_missing_returns_none(tmp_path: Path):
    assert read_last_run(tmp_path / "no.json") is None
