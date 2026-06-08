"""Per-symbol trade-print rolling spike detector for floor_trading.

A spike fires when the rolling rate of trade-print volume in the last
``burst_window_seconds`` is at least ``spike_volume_multiplier`` times the
rolling rate over the prior ``baseline_window_seconds``. Direction is
determined by the VWAP of the burst window vs the VWAP of the baseline
window — burst VWAP below baseline VWAP signals capitulation (down-spike);
burst VWAP above signals euphoria (up-spike).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto

from alpha_engine.strategies.floor_trading.params import FloorTradingParams


@dataclass(frozen=True)
class TradePrint:
    """A single executed trade — Nautilus-free analogue of `TradeTick`."""

    symbol: str
    ts: datetime
    price: float
    size: float


class SpikeKind(Enum):
    NONE = auto()
    DOWN = auto()  # burst VWAP < baseline VWAP (capitulation)
    UP = auto()  # burst VWAP > baseline VWAP (euphoria)


@dataclass(frozen=True)
class SpikeEvent:
    """Result of one spike-detector evaluation."""

    kind: SpikeKind
    symbol: str
    ts: datetime
    burst_vwap: float = 0.0
    baseline_vwap: float = 0.0


class SpikeDetector:
    """Maintains per-symbol rolling-window state and evaluates spikes per print.

    Memory cost: bounded by (burst + baseline) window in seconds x print rate.
    A 125-second window on a 5000-prints/sec mega-cap = ~625k entries worst case;
    typical mid-cap is well under 10k. Each entry is 24 bytes (datetime + float + float).
    """

    def __init__(self, params: FloorTradingParams) -> None:
        self._params = params
        self._prints: dict[str, deque[tuple[datetime, float, float]]] = {}

    def on_print(self, print_: TradePrint) -> SpikeEvent:
        history = self._prints.setdefault(print_.symbol, deque())
        history.append((print_.ts, print_.price, print_.size))

        total_window = self._params.burst_window_seconds + self._params.baseline_window_seconds
        cutoff = print_.ts - timedelta(seconds=total_window)

        while history and history[0][0] < cutoff:
            history.popleft()

        burst_start = print_.ts - timedelta(seconds=self._params.burst_window_seconds)
        # baseline_start equals the eviction cutoff above by construction, so no
        # retained print falls into an uncounted gap between baseline and eviction.
        baseline_start = burst_start - timedelta(seconds=self._params.baseline_window_seconds)

        burst_vol = 0.0
        burst_pv = 0.0
        baseline_vol = 0.0
        baseline_pv = 0.0

        for ts, price, size in history:
            if ts >= burst_start:
                burst_vol += size
                burst_pv += price * size
            elif ts >= baseline_start:
                baseline_vol += size
                baseline_pv += price * size

        if baseline_vol <= 0.0 or burst_vol <= 0.0:
            return SpikeEvent(kind=SpikeKind.NONE, symbol=print_.symbol, ts=print_.ts)

        burst_rate = burst_vol / self._params.burst_window_seconds
        baseline_rate = baseline_vol / self._params.baseline_window_seconds

        if burst_rate < self._params.spike_volume_multiplier * baseline_rate:
            return SpikeEvent(kind=SpikeKind.NONE, symbol=print_.symbol, ts=print_.ts)

        burst_vwap = burst_pv / burst_vol
        baseline_vwap = baseline_pv / baseline_vol

        if burst_vwap < baseline_vwap:
            kind = SpikeKind.DOWN
        elif burst_vwap > baseline_vwap:
            kind = SpikeKind.UP
        else:
            kind = SpikeKind.NONE
            
        return SpikeEvent(
            kind=kind,
            symbol=print_.symbol,
            ts=print_.ts,
            burst_vwap=burst_vwap,
            baseline_vwap=baseline_vwap,
        )
