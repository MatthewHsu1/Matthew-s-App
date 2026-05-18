"""Pure Day-1 setup detection — single source of truth for the bband+volume rule.

Both the live state machine and the vectorized scan layer consume this. If they
ever produce different setup counts on the same data, this module is the truth
and the caller is wrong.

NOTE (FUTURE GENERICNESS): This module is strategy-specific to bband_volume_setup.
When a second strategy is added to the research scan layer, this surface MUST be
promoted to a generic `StrategyScanProtocol` (or similar) defining a pure
`detect_setups(bars) -> SetupCandidate[]` contract. See the plan at
docs/superpowers/plans/2026-05-17-bband-vectorized-scan.md ("FUTURE WORK —
strategy genericness") for the refactor sketch. Do NOT copy this module to add
a second strategy; promote it first.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from alpha_engine.strategies.bband_volume_setup.params import (
    BBandVolumeSetupParams,
)


@dataclass(frozen=True)
class Day1Inputs:
    """Inputs to the Day-1 trigger evaluation for a single bar.

    `prior_closes` and `prior_volumes` are the rolling-window history BEFORE
    today's bar. The state machine pops/appends as bars arrive; the scan
    slices directly from a DataFrame. The detection function doesn't care.
    """
    prior_closes: Sequence[float]
    prior_volumes: Sequence[float]
    bar_low: float
    bar_volume: float


def _stddev(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


def is_day1_setup(inputs: Day1Inputs, params: BBandVolumeSetupParams) -> bool:
    """Return True iff the current bar trips the Day-1 trigger rule.

    Rule: bar.low <= lower BBand AND bar.volume >= multiplier * avg(prior volumes).
    Lower BBand = SMA(prior closes) - stddev_multiplier * stddev(prior closes).
    Requires a full window of prior data; partial windows return False.
    """
    if len(inputs.prior_closes) < params.bband_period:
        return False
    if len(inputs.prior_volumes) < params.volume_avg_period:
        return False

    closes = list(inputs.prior_closes)
    sma = sum(closes) / len(closes)
    lower_band = sma - params.bband_stddev * _stddev(closes)
    avg_volume = sum(inputs.prior_volumes) / len(inputs.prior_volumes)

    volume_trigger = inputs.bar_volume >= params.day1_volume_multiplier * avg_volume
    band_trigger = inputs.bar_low <= lower_band
    return volume_trigger and band_trigger
