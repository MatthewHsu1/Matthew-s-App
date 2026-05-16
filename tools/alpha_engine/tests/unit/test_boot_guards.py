from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_engine.control.boot_guards import (
    BootRefusedError,
    assert_safe_to_boot,
)


def test_safe_when_no_killfile_no_last_run(tmp_path: Path):
    assert_safe_to_boot(
        killfile_path=tmp_path / ".KILL",
        last_run_path=tmp_path / "last_run.json",
    )


def test_refuses_when_killfile_present(tmp_path: Path):
    (tmp_path / ".KILL").touch()
    with pytest.raises(BootRefusedError, match="kill-switch active"):
        assert_safe_to_boot(
            killfile_path=tmp_path / ".KILL",
            last_run_path=tmp_path / "last_run.json",
        )


def test_refuses_when_pid_in_last_run_is_alive(tmp_path: Path):
    last_run = tmp_path / "last_run.json"
    last_run.write_text(json.dumps({
        "pid": os.getpid(),
        "started_ts": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "run_id": "r",
        "env_name": "e",
        "heartbeat_ts": datetime.now(timezone.utc).isoformat(),
    }))
    with pytest.raises(BootRefusedError, match="already running"):
        assert_safe_to_boot(
            killfile_path=tmp_path / ".KILL",
            last_run_path=last_run,
        )


def test_ok_when_pid_in_last_run_is_dead(tmp_path: Path):
    last_run = tmp_path / "last_run.json"
    last_run.write_text(json.dumps({
        "pid": 999_999,  # almost certainly dead
        "started_ts": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "run_id": "r",
        "env_name": "e",
        "heartbeat_ts": datetime.now(timezone.utc).isoformat(),
    }))
    # Should not raise; stale last_run is OK.
    assert_safe_to_boot(
        killfile_path=tmp_path / ".KILL",
        last_run_path=last_run,
    )
