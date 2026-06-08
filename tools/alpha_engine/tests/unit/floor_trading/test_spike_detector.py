"""SpikeDetector unit tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpha_engine.strategies.floor_trading.params import FloorTradingParams
from alpha_engine.strategies.floor_trading.spike_detector import (
    SpikeDetector,
    SpikeKind,
    TradePrint,
)

_T0 = datetime(2026, 1, 5, 14, 30, 0, tzinfo=timezone.utc)  # 9:30 ET


def _params(**overrides) -> FloorTradingParams:
    return FloorTradingParams(**overrides)


def _feed_baseline(
    det: SpikeDetector, symbol: str, *,
    start: datetime, n_prints: int, price: float, size: float,
) -> datetime:
    """Feed n_prints evenly spaced across the detector's baseline window. Returns the timestamp of the last seeded print."""
    last = start
    window_seconds = det._params.baseline_window_seconds
    step = timedelta(seconds=window_seconds / n_prints)

    for i in range(n_prints):
        last = start + step * i
        det.on_print(TradePrint(symbol=symbol, ts=last, price=price, size=size))
        
    return last


def test_empty_history_no_spike() -> None:
    det = SpikeDetector(_params())
    event = det.on_print(TradePrint(symbol="X", ts=_T0, price=100.0, size=100.0))
    assert event.kind is SpikeKind.NONE


def test_zero_baseline_volume_suppresses_spike() -> None:
    # Only one print, no baseline volume ⇒ no spike can fire.
    det = SpikeDetector(_params())
    event = det.on_print(TradePrint(symbol="X", ts=_T0, price=100.0, size=10_000.0))
    assert event.kind is SpikeKind.NONE


def test_down_spike_on_burst_with_lower_vwap() -> None:
    det = SpikeDetector(_params())
    # Seed 2 minutes of steady prints at price 100, total volume 12000 (= 100 shares/sec baseline rate).
    _feed_baseline(det, "X", start=_T0, n_prints=120, price=100.0, size=100.0)
    # Now in the burst window (next 5 seconds after 2 min), inject a sustained burst at price 98 (lower).
    # Burst rate must be >= 10 * baseline_rate (100/s) = 1000 shares/sec. 5s x 1000 = 5000 shares minimum.
    burst_t = _T0 + timedelta(seconds=120.0)
    event = det.on_print(TradePrint(symbol="X", ts=burst_t + timedelta(seconds=4.5), price=98.0, size=6_000.0))
    assert event.kind is SpikeKind.DOWN
    assert event.burst_vwap < event.baseline_vwap


def test_up_spike_on_burst_with_higher_vwap() -> None:
    det = SpikeDetector(_params())
    _feed_baseline(det, "X", start=_T0, n_prints=120, price=100.0, size=100.0)
    burst_t = _T0 + timedelta(seconds=120.0)
    event = det.on_print(TradePrint(symbol="X", ts=burst_t + timedelta(seconds=4.5), price=102.0, size=6_000.0))
    assert event.kind is SpikeKind.UP
    assert event.burst_vwap > event.baseline_vwap


def test_burst_below_10x_does_not_fire() -> None:
    det = SpikeDetector(_params())
    _feed_baseline(det, "X", start=_T0, n_prints=120, price=100.0, size=100.0)
    burst_t = _T0 + timedelta(seconds=120.0)
    # 5s x 800 shares/sec = 4000 -- below the 10x (= 1000/s baseline) threshold.
    event = det.on_print(TradePrint(symbol="X", ts=burst_t + timedelta(seconds=4.5), price=98.0, size=4_000.0))
    assert event.kind is SpikeKind.NONE


def test_equal_vwap_is_no_op() -> None:
    det = SpikeDetector(_params())
    _feed_baseline(det, "X", start=_T0, n_prints=120, price=100.0, size=100.0)
    burst_t = _T0 + timedelta(seconds=120.0)
    # Burst price exactly equals baseline VWAP (100.0).
    event = det.on_print(TradePrint(symbol="X", ts=burst_t + timedelta(seconds=4.5), price=100.0, size=6_000.0))
    assert event.kind is SpikeKind.NONE
    # Verify the equal-VWAP branch was reached (not the rate-threshold short-circuit).
    assert event.burst_vwap == 100.0
    assert event.baseline_vwap == 100.0


def test_old_prints_are_evicted() -> None:
    det = SpikeDetector(_params())
    # Print far in the past should not appear in baseline.
    det.on_print(TradePrint(symbol="X", ts=_T0 - timedelta(minutes=10), price=100.0, size=1_000_000.0))
    # New print at _T0 sees no baseline ⇒ no spike.
    event = det.on_print(TradePrint(symbol="X", ts=_T0, price=98.0, size=10_000.0))
    assert event.kind is SpikeKind.NONE


def test_per_symbol_isolation() -> None:
    det = SpikeDetector(_params())
    _feed_baseline(det, "X", start=_T0, n_prints=120, price=100.0, size=100.0)
    # Symbol Y has empty history. Even with a huge print, no spike.
    event = det.on_print(TradePrint(symbol="Y", ts=_T0 + timedelta(seconds=125), price=98.0, size=100_000.0))
    assert event.kind is SpikeKind.NONE
