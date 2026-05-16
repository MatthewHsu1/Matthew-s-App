from __future__ import annotations

from pathlib import Path

import pytest

from alpha_engine.engine.paper import install_kill_switch_poller


def test_poller_runs_full_sequence_when_killfile_appears(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    calls = []

    poller = install_kill_switch_poller(
        killfile_path=killfile,
        cancel_all=lambda: calls.append("cancel"),
        flatten=lambda: calls.append("flatten"),
        write_summary=lambda cause: calls.append(f"summary:{cause}"),
        flatten_on_halt=True,
    )

    # No killfile → no-op ticks.
    for _ in range(3):
        poller.tick()
    assert calls == []

    # Create killfile, tick once → halt sequence runs.
    killfile.touch()
    assert poller.tick() is True
    assert calls == ["cancel", "flatten", "summary:kill_switch"]

    # Subsequent ticks are idempotent.
    poller.tick()
    poller.tick()
    assert calls == ["cancel", "flatten", "summary:kill_switch"]


def test_poller_respects_flatten_disabled(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    calls = []

    poller = install_kill_switch_poller(
        killfile_path=killfile,
        cancel_all=lambda: calls.append("cancel"),
        flatten=lambda: calls.append("flatten"),
        write_summary=lambda cause: calls.append("summary"),
        flatten_on_halt=False,
    )
    killfile.touch()
    poller.tick()
    assert calls == ["cancel", "summary"]
