from __future__ import annotations

from alpha_engine.strategies.bband_volume_setup.detection import (
    Day1Inputs,
    is_day1_setup,
)
from alpha_engine.strategies.bband_volume_setup.state_machine import (
    BBandVolumeSetupParams,
)


def _params(**overrides) -> BBandVolumeSetupParams:
    base = dict(
        bband_period=20, bband_stddev=2.0, volume_avg_period=20,
        day1_volume_multiplier=2.0, spike_volume_multiplier=3.0,
        spike_price_move_pct=1.5, surge_volume_multiplier=2.0,
        surge_requires_price_below_open=True, surge_min_gap_minutes=30,
        tranche_count=3, hard_stop_pct_below_day1_low=2.0, max_hold_days=5,
    )
    base.update(overrides)
    return BBandVolumeSetupParams(**base)


def test_returns_false_when_history_too_short() -> None:
    inputs = Day1Inputs(
        prior_closes=[100.0] * 5,
        prior_volumes=[1_000_000.0] * 5,
        bar_low=99.0,
        bar_volume=2_500_000.0,
    )
    assert is_day1_setup(inputs, _params()) is False


def test_returns_false_when_volume_normal() -> None:
    closes = [100.0 + (1.5 if i % 2 == 0 else -1.5) for i in range(20)]
    inputs = Day1Inputs(
        prior_closes=closes,
        prior_volumes=[1_000_000.0] * 20,
        bar_low=96.0,           # below lower band
        bar_volume=1_000_000.0, # only 1x avg
    )
    assert is_day1_setup(inputs, _params()) is False


def test_returns_false_when_price_inside_band() -> None:
    closes = [100.0 + (1.5 if i % 2 == 0 else -1.5) for i in range(20)]
    inputs = Day1Inputs(
        prior_closes=closes,
        prior_volumes=[1_000_000.0] * 20,
        bar_low=99.0,           # well inside band
        bar_volume=2_500_000.0, # 2.5x avg
    )
    assert is_day1_setup(inputs, _params()) is False


def test_returns_true_when_both_conditions_met() -> None:
    closes = [100.0 + (1.5 if i % 2 == 0 else -1.5) for i in range(20)]
    inputs = Day1Inputs(
        prior_closes=closes,
        prior_volumes=[1_000_000.0] * 20,
        bar_low=96.0,            # below lower band ~97
        bar_volume=2_500_000.0,  # 2.5x avg
    )
    assert is_day1_setup(inputs, _params()) is True
