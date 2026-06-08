"""Pure Day-1 setup detection for floor_trading.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from alpha_engine.strategies.floor_trading.params import FloorTradingParams


@dataclass(frozen=True)
class Day1Inputs:
    """Inputs to the Day-1 trigger evaluation for a single closed daily bar.

    `prior_closes` and `prior_volumes` are the rolling-window history BEFORE
    today's bar. State machine pops/appends as bars arrive; scan slices a
    DataFrame. The detection function doesn't care.
    """
    prior_closes: Sequence[float]
    prior_volumes: Sequence[float]
    bar_low: float
    bar_volume: float


def _stddev_population(values: Sequence[float]) -> float:
    n = len(values)

    if n < 2:
        return 0.0
    
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n

    return math.sqrt(var)


def is_day1_setup(inputs: Day1Inputs, params: FloorTradingParams) -> bool:
    """Return True iff the bar trips Floor Trading's Day-1 rule.

    Rule: bar.low <= lower_BBand AND bar.volume >= multiplier * avg(prior_volumes).
    Lower BBand = SMA(prior_closes) - stddev_multiplier * stddev(prior_closes).
    Requires full window of prior data; partial windows return False.
    """
    if len(inputs.prior_closes) < params.bband_period:
        return False
    
    if len(inputs.prior_volumes) < params.volume_avg_period:
        return False

    closes = list(inputs.prior_closes)
    sma = sum(closes) / len(closes)
    lower_band = sma - params.bband_stddev * _stddev_population(closes)
    avg_volume = sum(inputs.prior_volumes) / len(inputs.prior_volumes)

    volume_trigger = inputs.bar_volume >= params.day1_volume_multiplier * avg_volume
    band_trigger = inputs.bar_low <= lower_band

    return volume_trigger and band_trigger
