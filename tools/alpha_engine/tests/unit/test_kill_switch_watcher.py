from __future__ import annotations

from pathlib import Path

from alpha_engine.risk.kill_switch_watcher import KillSwitchWatcher


def test_no_killfile_means_not_triggered(tmp_path: Path):
    w = KillSwitchWatcher(killfile_path=tmp_path / ".KILL")
    assert not w.triggered()


def test_killfile_present_means_triggered(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    killfile.touch()
    w = KillSwitchWatcher(killfile_path=killfile)
    assert w.triggered()


def test_run_halt_sequence_calls_callbacks_in_order(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    killfile.touch()
    calls = []
    w = KillSwitchWatcher(killfile_path=killfile)
    w.run_halt_sequence(
        cancel_all=lambda: calls.append("cancel"),
        flatten=lambda: calls.append("flatten"),
        write_summary=lambda halt_cause: calls.append(f"summary:{halt_cause}"),
    )
    assert calls == ["cancel", "flatten", "summary:kill_switch"]


def test_halt_sequence_skips_flatten_when_disabled(tmp_path: Path):
    killfile = tmp_path / ".KILL"
    killfile.touch()
    calls = []
    w = KillSwitchWatcher(killfile_path=killfile, flatten_on_halt=False)
    w.run_halt_sequence(
        cancel_all=lambda: calls.append("cancel"),
        flatten=lambda: calls.append("flatten"),
        write_summary=lambda halt_cause: calls.append("summary"),
    )
    assert calls == ["cancel", "summary"]
