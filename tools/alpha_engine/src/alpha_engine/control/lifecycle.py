"""Lifecycle backend: PID liveness, SIGTERM-with-timeout, JSONL tail."""
from __future__ import annotations

import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def is_pid_alive(pid: int) -> bool:
    # Opportunistically reap if pid is our own child; harmless otherwise.
    # Without this, a zombie child would look "alive" to os.kill(pid, 0)
    # because zombies still occupy the process table.
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, ProcessLookupError):
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # PID exists but is owned by another user; still "alive".
        return True
    return True


def is_heartbeat_stale(
    heartbeat_iso: str,
    *,
    threshold_s: float,
    now: datetime | None = None,
) -> bool:
    hb = datetime.fromisoformat(heartbeat_iso)
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=timezone.utc)
    current = now or datetime.now(tz=timezone.utc)
    return (current - hb).total_seconds() > threshold_s


def stop_pid_with_timeout(pid: int, *, timeout_s: float = 30.0) -> bool:
    """Send SIGTERM, wait up to `timeout_s`, then SIGKILL. Returns True if stopped."""
    if not is_pid_alive(pid):
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.1)
    # SIGTERM didn't work; escalate.
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    time.sleep(0.2)
    return not is_pid_alive(pid)


def tail_jsonl(path: Path, *, follow: bool = True) -> Iterator[str]:
    """Generator yielding lines from a JSONL file; blocks for new lines when `follow=True`."""
    if not path.exists():
        if not follow:
            return
        # Wait for the file to appear.
        while not path.exists():
            time.sleep(0.5)
    with open(path, "r") as f:
        # Yield existing content.
        for line in f:
            yield line.rstrip("\n")
        if not follow:
            return
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                time.sleep(0.5)
                f.seek(pos)
                continue
            yield line.rstrip("\n")
