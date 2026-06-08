"""Per-symbol rolling-window driver for Floor Trading's Day-1 scan.

Used by FloorScanActor. Kept Nautilus-free so the detection logic can be
unit-tested with synthetic daily bars in milliseconds. The actor calls
on_daily_bar on every closed daily bar; this module manages the rolling
window of prior closes + volumes and packages a SetupDetected payload
whenever is_day1_setup fires.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from alpha_engine.scan.setup_detected import SetupDetected
from alpha_engine.strategies.floor_trading.detection import Day1Inputs, is_day1_setup
from alpha_engine.strategies.floor_trading.params import FloorTradingParams


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


class FloorScanLogic:
    """Per-symbol rolling windows + Day-1 trigger evaluation."""

    def __init__(self, params: FloorTradingParams) -> None:
        self._params = params
        self._windows: dict[str, _SymbolWindow] = {}

    def on_daily_bar(self, bar: ScanBar) -> SetupDetected | None:
        """Evaluate today's bar against the prior-window baseline, then append.

        Append happens AFTER evaluation so today's volume cannot inflate its
        own baseline.
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
        """Return the current count of bars in the rolling window for `symbol`.

        Used by tests to verify the rolling window is bounded by `bband_period`.
        Returns 0 for unknown symbols.
        """
        window = self._windows.get(symbol)
        return 0 if window is None else len(window.closes)
