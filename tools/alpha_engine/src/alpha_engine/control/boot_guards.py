"""Pre-boot safety checks: refuse to start if kill-switch is active or PID is live."""
from __future__ import annotations

from pathlib import Path

from alpha_engine.control.last_run import read_last_run
from alpha_engine.control.lifecycle import is_pid_alive


class BootRefusedError(RuntimeError):
    pass


def assert_safe_to_boot(
    *,
    killfile_path: Path,
    last_run_path: Path,
) -> None:
    if killfile_path.exists():
        raise BootRefusedError(
            f"kill-switch active — remove {killfile_path} to start"
        )
    data = read_last_run(last_run_path)
    if data is not None:
        pid = data.get("pid")
        if isinstance(pid, int) and is_pid_alive(pid):
            raise BootRefusedError(
                f"env already running (PID {pid}) — use `env stop` first"
            )
