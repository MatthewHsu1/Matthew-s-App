"""Polls a `.KILL` file. When present, executes a halt sequence.

Phase 2 wires this via a Nautilus TimeEvent in engine/paper.py (Task 29).
The watcher itself is pure I/O so it's unit-testable without Nautilus.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable


class KillSwitchWatcher:
    def __init__(
        self,
        *,
        killfile_path: Path,
        flatten_on_halt: bool = True,
    ):
        self._killfile = Path(killfile_path)
        self._flatten = flatten_on_halt

    @property
    def killfile_path(self) -> Path:
        return self._killfile

    def triggered(self) -> bool:
        return self._killfile.exists()

    def run_halt_sequence(
        self,
        *,
        cancel_all: Callable[[], None],
        flatten: Callable[[], None],
        write_summary: Callable[[str], None],
    ) -> None:
        cancel_all()
        if self._flatten:
            flatten()
        write_summary("kill_switch")
