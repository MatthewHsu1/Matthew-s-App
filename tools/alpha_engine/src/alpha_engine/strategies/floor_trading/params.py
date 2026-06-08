"""Strategy parameter dataclass for floor_trading.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FloorTradingParams:
    # Day-1 detector (canonical Bollinger settings).
    bband_period: int = 20
    bband_stddev: float = 2.0
    volume_avg_period: int = 20
    day1_volume_multiplier: float = 2.0

    # Spike detector (trade-print based).
    burst_window_seconds: float = 5.0
    baseline_window_seconds: float = 120.0
    spike_volume_multiplier: float = 10.0

    # Stop-loss (reference is T1 fill price, locked).
    stop_pct_below_t1: float = 1.5

    # Position lifecycle.
    tranche_count: int = 2
    max_hold_days: int = 3  # Day 2 entry → Day 4 forced exit
