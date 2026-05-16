from __future__ import annotations

from pathlib import Path

from alpha_engine.config.paths import EnvPaths
from alpha_engine.control.last_run import read_last_run
from alpha_engine.control.lifecycle import is_pid_alive, stop_pid_with_timeout


def run(*, envs_root: Path, name: str, timeout_s: float = 30.0) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    data = read_last_run(paths.last_run_path)
    if data is None:
        print(f"no last_run.json for env {name!r}", flush=True)
        return 1
    pid = data.get("pid")
    if not isinstance(pid, int):
        print(f"last_run.json for {name!r} has no PID", flush=True)
        return 2
    if not is_pid_alive(pid):
        print(f"env {name!r} not running (stale PID {pid}); cleaning up", flush=True)
        return 0
    ok = stop_pid_with_timeout(pid, timeout_s=timeout_s)
    if not ok:
        print(f"failed to stop PID {pid} within {timeout_s}s", flush=True)
        return 3
    print(f"stopped env {name!r} (PID {pid})", flush=True)
    return 0
