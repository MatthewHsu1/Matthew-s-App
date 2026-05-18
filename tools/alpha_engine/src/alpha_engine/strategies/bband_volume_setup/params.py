"""Strategy parameter dataclass for bband_volume_setup.

Extracted into its own module to break a circular import between
``state_machine.py`` (state + transitions) and ``detection.py`` (the pure
Day-1 rule). Both modules import :class:`BBandVolumeSetupParams` from here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBandVolumeSetupParams:
    bband_period: int = 20
    bband_stddev: float = 2.0
    volume_avg_period: int = 20
    day1_volume_multiplier: float = 2.0
    spike_volume_multiplier: float = 3.0
    spike_price_move_pct: float = 1.5
    surge_volume_multiplier: float = 2.0
    surge_requires_price_below_open: bool = True
    surge_min_gap_minutes: int = 30
    tranche_count: int = 3
    hard_stop_pct_below_day1_low: float = 2.0
    max_hold_days: int = 5
