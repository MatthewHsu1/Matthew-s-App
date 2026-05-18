"""Pure-Python rolling-window driver for the BBand+volume Day-1 detection.

Used by `BBandScanActor`. Kept Nautilus-free so the detection logic can be
unit-tested with synthetic bars in milliseconds. `is_day1_setup` is reused
verbatim — this module only manages the rolling window and packaging.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from alpha_engine.scan.setup_detected import SetupDetected
from alpha_engine.strategies.bband_volume_setup.detection import (
    Day1Inputs,
    is_day1_setup,
)
from alpha_engine.strategies.bband_volume_setup.params import (
    BBandVolumeSetupParams,
)


@dataclass(frozen=True)
class ScanBar:
    """Minimal daily-bar tuple consumed by the scan logic."""

    symbol: str
    ts: datetime
    low: float
    close: float
    volume: float


class _SymbolWindow:
    __slots__ = ("closes", "volumes")

    def __init__(self) -> None:
        self.closes: deque[float] = deque()
        self.volumes: deque[float] = deque()


class BBandScanLogic:
    """Per-symbol rolling windows + Day-1 trigger evaluation."""

    def __init__(self, params: BBandVolumeSetupParams) -> None:
        self._params = params
        self._windows: dict[str, _SymbolWindow] = {}

    def on_daily_bar(self, bar: ScanBar) -> SetupDetected | None:
        """Evaluate today's bar against the prior-window baseline, then append.

        Returns a `SetupDetected` payload iff `is_day1_setup` fires. Append
        happens AFTER evaluation so today's volume cannot inflate today's
        baseline (mirrors `BBandVolumeSetupStateMachine.on_daily_bar`).
        """
        window = self._windows.setdefault(bar.symbol, _SymbolWindow())

        inputs = Day1Inputs(
            prior_closes=list(window.closes),
            prior_volumes=list(window.volumes),
            bar_low=bar.low,
            bar_volume=bar.volume,
        )
        result: SetupDetected | None = None
        if is_day1_setup(inputs, self._params):
            result = SetupDetected(
                symbol=bar.symbol,
                ts=bar.ts,
                day1_close=bar.close,
                day1_low=bar.low,
            )

        window.closes.append(bar.close)
        window.volumes.append(bar.volume)
        if len(window.closes) > self._params.bband_period:
            window.closes.popleft()
        if len(window.volumes) > self._params.volume_avg_period:
            window.volumes.popleft()

        return result

    def window_size(self, symbol: str) -> int:
        window = self._windows.get(symbol)
        return 0 if window is None else len(window.closes)
