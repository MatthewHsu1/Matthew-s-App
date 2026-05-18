from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from alpha_engine.cli_commands.env_stop import run as env_stop


def _write_last_run(path: Path, pid: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "pid": pid,
        "started_ts": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "run_id": "r",
        "env_name": "e",
        "heartbeat_ts": datetime.now(timezone.utc).isoformat(),
    }))


def test_no_last_run_returns_nonzero(tmp_path: Path, capsys):
    code = env_stop(envs_root=tmp_path, name="missing")
    assert code != 0
    captured = capsys.readouterr()
    assert "no last_run.json" in captured.out or "no last_run.json" in captured.err


def test_dead_pid_cleans_up_returns_zero(tmp_path: Path):
    env_dir = tmp_path / "test_env"
    last_run = env_dir / "state" / "last_run.json"
    _write_last_run(last_run, pid=999_999)
    code = env_stop(envs_root=tmp_path, name="test_env")
    assert code == 0


def test_live_pid_is_terminated(tmp_path: Path):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        env_dir = tmp_path / "test_env"
        last_run = env_dir / "state" / "last_run.json"
        _write_last_run(last_run, pid=proc.pid)
        code = env_stop(envs_root=tmp_path, name="test_env", timeout_s=2.0)
        assert code == 0
        # Reap the zombie so poll() sees exit.
        proc.wait(timeout=1.0)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
