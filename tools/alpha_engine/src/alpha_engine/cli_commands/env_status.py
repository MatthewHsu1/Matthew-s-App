from __future__ import annotations

from pathlib import Path

from alpha_engine.config.paths import EnvPaths
from alpha_engine.control.last_run import read_last_run
from alpha_engine.control.lifecycle import is_heartbeat_stale, is_pid_alive

HEARTBEAT_STALE_S = 60.0


def run(*, envs_root: Path, name: str) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    data = read_last_run(paths.last_run_path)
    if data is None:
        print(f"env {name!r}: no last_run.json (not started)", flush=True)
        return 1
    pid = data.get("pid")
    mode = data.get("mode", "?")
    run_id = data.get("run_id", "?")
    heartbeat = data.get("heartbeat_ts", "")
    alive = isinstance(pid, int) and is_pid_alive(pid)
    stale = bool(heartbeat) and is_heartbeat_stale(heartbeat, threshold_s=HEARTBEAT_STALE_S)
    state = "alive" if alive else "dead PID (not running)"
    if alive and stale:
        state += " — stale heartbeat"
    print(f"env {name!r}: {state}", flush=True)
    print(f"  pid={pid} mode={mode} run_id={run_id}", flush=True)
    print(f"  heartbeat_ts={heartbeat}", flush=True)
    return 0
