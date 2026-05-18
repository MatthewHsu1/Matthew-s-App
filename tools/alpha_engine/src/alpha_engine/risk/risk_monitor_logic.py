"""Pure-Python halt-condition driver for `RiskMonitorActor`.

Three independent halt conditions:
  * max_daily_loss — account equity drop exceeds threshold vs session start
  * outside_market_hours — wall-clock outside [open, close]
  * kill_switch_file — operator-created flag file present

Once any condition fires, the logic is one-way `halted=True`. Re-evaluating
returns None forever (operator restarts to recover). Mirrors the spec's
"halts are one-way for the session" rule (§6.2).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum, auto


class HaltReason(Enum):
    MAX_DAILY_LOSS = auto()
    OUTSIDE_MARKET_HOURS = auto()
    KILL_SWITCH_FILE = auto()


@dataclass(frozen=True)
class RiskMonitorConfig:
    max_daily_loss_usd: float
    session_open_et: time
    session_close_et: time


class RiskMonitorLogic:
    def __init__(self, cfg: RiskMonitorConfig) -> None:
        self._cfg = cfg
        self._baseline: float | None = None
        self._halted: bool = False

    @property
    def halted(self) -> bool:
        return self._halted

    def set_session_baseline(self, equity: float) -> None:
        self._baseline = equity

    def on_equity(self, equity: float) -> HaltReason | None:
        if self._halted or self._baseline is None:
            return None
        drop = self._baseline - equity
        if drop >= self._cfg.max_daily_loss_usd:
            self._halted = True
            return HaltReason.MAX_DAILY_LOSS
        return None

    def tick(self, *, now: datetime, kill_file_exists: bool) -> HaltReason | None:
        if self._halted:
            return None
        if kill_file_exists:
            self._halted = True
            return HaltReason.KILL_SWITCH_FILE
        wall = now.time()
        if wall < self._cfg.session_open_et or wall > self._cfg.session_close_et:
            self._halted = True
            return HaltReason.OUTSIDE_MARKET_HOURS
        return None
