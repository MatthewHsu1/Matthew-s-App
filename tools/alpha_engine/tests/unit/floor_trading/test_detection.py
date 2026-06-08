"""Day-1 setup detector unit tests for floor_trading.
"""
from __future__ import annotations

from alpha_engine.strategies.floor_trading.detection import Day1Inputs, is_day1_setup
from alpha_engine.strategies.floor_trading.params import FloorTradingParams


def _make_params(**overrides) -> FloorTradingParams:
    return FloorTradingParams(**overrides)


def test_partial_window_returns_false() -> None:
    # Fewer than bband_period prior closes ⇒ setup cannot fire.
    inputs = Day1Inputs(
        prior_closes=[100.0] * 5,
        prior_volumes=[1000.0] * 5,
        bar_low=80.0,
        bar_volume=10_000.0,
    )
    assert is_day1_setup(inputs, _make_params()) is False


def test_band_touch_with_heavy_volume_fires() -> None:
    closes = [100.0] * 20
    volumes = [1000.0] * 20
    # Lower band = mean - 2*stddev. stddev=0 here, so lower band = 100.0.
    # bar.low = 99.9 < 100.0 ⇒ touches/breaks below.
    inputs = Day1Inputs(
        prior_closes=closes, prior_volumes=volumes,
        bar_low=99.9, bar_volume=3_000.0,  # 3x avg volume ≥ 2x threshold
    )
    assert is_day1_setup(inputs, _make_params()) is True


def test_band_touch_without_volume_does_not_fire() -> None:
    closes = [100.0] * 20
    volumes = [1000.0] * 20
    inputs = Day1Inputs(
        prior_closes=closes, prior_volumes=volumes,
        bar_low=99.9, bar_volume=1_999.0,  # just below 2x avg
    )
    assert is_day1_setup(inputs, _make_params()) is False


def test_heavy_volume_without_band_touch_does_not_fire() -> None:
    # Vary the closes so stddev > 0, giving a meaningful lower band.
    closes = [100.0 + (i % 2) * 2.0 for i in range(20)]  # alternates 100/102
    volumes = [1000.0] * 20
    # bar.low above the lower band.
    inputs = Day1Inputs(
        prior_closes=closes, prior_volumes=volumes,
        bar_low=99.9, bar_volume=5_000.0,
    )
    # Lower band = mean(101) - 2 * stddev(~1) ≈ 99 → bar.low 99.9 is ABOVE band → no trigger
    assert is_day1_setup(inputs, _make_params()) is False


def test_inclusive_band_touch_at_exactly_lower_band_fires() -> None:
    closes = [100.0] * 20
    volumes = [1000.0] * 20
    # stddev=0 ⇒ lower band = mean = 100.0
    inputs = Day1Inputs(
        prior_closes=closes, prior_volumes=volumes,
        bar_low=100.0,  # exact touch
        bar_volume=3_000.0,
    )
    assert is_day1_setup(inputs, _make_params()) is True


def test_inclusive_volume_at_exactly_2x_fires() -> None:
    closes = [100.0] * 20
    volumes = [1000.0] * 20
    inputs = Day1Inputs(
        prior_closes=closes, prior_volumes=volumes,
        bar_low=99.9, bar_volume=2_000.0,  # exactly 2x avg
    )
    assert is_day1_setup(inputs, _make_params()) is True
