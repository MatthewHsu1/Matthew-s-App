from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from alpha_engine.control.lifecycle import (
    is_pid_alive,
    is_heartbeat_stale,
    stop_pid_with_timeout,
)


def test_is_pid_alive_for_self():
    assert is_pid_alive(os.getpid())


def test_is_pid_alive_for_garbage_pid():
    # PID 999_999 is almost certainly not running.
    assert not is_pid_alive(999_999)


def test_is_heartbeat_stale_when_older_than_threshold():
    now = datetime(2026, 5, 16, 14, 30, tzinfo=timezone.utc)
    old = (now - timedelta(seconds=300)).isoformat()
    assert is_heartbeat_stale(old, threshold_s=60, now=now)


def test_is_heartbeat_fresh_when_recent():
    now = datetime(2026, 5, 16, 14, 30, tzinfo=timezone.utc)
    recent = (now - timedelta(seconds=10)).isoformat()
    assert not is_heartbeat_stale(recent, threshold_s=60, now=now)


def test_stop_pid_with_timeout_sends_sigterm_then_returns_true():
    # Spawn a child that sleeps; SIGTERM should stop it cleanly.
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        ok = stop_pid_with_timeout(proc.pid, timeout_s=2.0)
        assert ok
        # Reap the zombie so is_pid_alive sees it gone (this test process is
        # the parent; in production env stop is a separate process so reaping
        # is the kernel's job).
        proc.wait(timeout=1.0)
        assert not is_pid_alive(proc.pid)
    finally:
        if proc.poll() is None:
            proc.kill()
