from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpha_engine.cli_commands.env_status import run as env_status


def _write_last_run(path: Path, pid: int, heartbeat: datetime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "pid": pid,
        "started_ts": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "run_id": "r",
        "env_name": "e",
        "heartbeat_ts": heartbeat.isoformat(),
    }))


def test_missing_env_returns_nonzero(tmp_path: Path, capsys):
    code = env_status(envs_root=tmp_path, name="nope")
    assert code != 0


def test_running_env_prints_alive(tmp_path: Path, capsys):
    p = tmp_path / "e" / "state" / "last_run.json"
    _write_last_run(p, os.getpid(), datetime.now(timezone.utc))
    code = env_status(envs_root=tmp_path, name="e")
    assert code == 0
    out = capsys.readouterr().out
    assert "alive" in out.lower() or "running" in out.lower()


def test_stale_heartbeat_flagged(tmp_path: Path, capsys):
    p = tmp_path / "e" / "state" / "last_run.json"
    _write_last_run(p, os.getpid(), datetime.now(timezone.utc) - timedelta(minutes=10))
    code = env_status(envs_root=tmp_path, name="e")
    out = capsys.readouterr().out
    assert "stale" in out.lower()


def test_dead_pid_flagged(tmp_path: Path, capsys):
    p = tmp_path / "e" / "state" / "last_run.json"
    _write_last_run(p, 999_999, datetime.now(timezone.utc))
    code = env_status(envs_root=tmp_path, name="e")
    out = capsys.readouterr().out
    assert "dead" in out.lower() or "not running" in out.lower()
