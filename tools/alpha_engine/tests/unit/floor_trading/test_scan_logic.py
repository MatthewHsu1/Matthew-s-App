"""FloorScanLogic per-symbol rolling-window driver tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpha_engine.scan.setup_detected import SetupDetected
from alpha_engine.strategies.floor_trading.params import FloorTradingParams
from alpha_engine.strategies.floor_trading.scan_logic import FloorScanLogic, ScanBar

_T0 = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def _params() -> FloorTradingParams:
    return FloorTradingParams()


def _bar(symbol: str, low: float, close: float, volume: float, day_offset: int = 0) -> ScanBar:
    return ScanBar(symbol=symbol, ts=_T0 + timedelta(days=day_offset), low=low, close=close, volume=volume)


def test_partial_window_returns_none() -> None:
    logic = FloorScanLogic(_params())
    result = logic.on_daily_bar(_bar("X", low=99.0, close=100.0, volume=5_000.0))
    assert result is None


def test_after_full_window_setup_fires_on_band_touch_with_heavy_volume() -> None:
    logic = FloorScanLogic(_params())
    # Feed 20 prior bars: close=100, volume=1000. No previous setup possible.
    for i in range(20):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    # 21st bar: low touches lower band (= 100.0 with zero stddev), volume = 3x avg.
    result = logic.on_daily_bar(_bar("X", low=99.5, close=99.5, volume=3_000.0, day_offset=20))
    assert isinstance(result, SetupDetected)
    assert result.symbol == "X"
    assert result.day1_close == 99.5
    assert result.day1_low == 99.5


def test_no_setup_when_volume_below_threshold() -> None:
    logic = FloorScanLogic(_params())
    for i in range(20):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    result = logic.on_daily_bar(_bar("X", low=99.9, close=99.5, volume=1_500.0, day_offset=20))  # only 1.5x
    assert result is None


def test_per_symbol_isolation() -> None:
    logic = FloorScanLogic(_params())
    for i in range(20):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    # Symbol Y has no history; the same Day-1-trigger-shaped bar yields nothing.
    result = logic.on_daily_bar(_bar("Y", low=99.9, close=99.5, volume=3_000.0, day_offset=20))
    assert result is None


def test_rolling_window_is_capped_at_bband_period() -> None:
    logic = FloorScanLogic(_params())
    # Feed 25 bars; window should cap at bband_period (=20).
    for i in range(25):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    assert logic.window_size("X") == 20
    # Unknown symbol returns 0.
    assert logic.window_size("Y") == 0


def test_setup_can_fire_again_after_window_eviction() -> None:
    logic = FloorScanLogic(_params())
    # Bars 0-19: flat baseline (close=100, volume=1000).
    for i in range(20):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    # Bar 20: first Day-1 trigger fires.
    first = logic.on_daily_bar(_bar("X", low=99.5, close=99.5, volume=3_000.0, day_offset=20))
    assert isinstance(first, SetupDetected)
    # Bars 21-40: flat baseline again (volumes back to 1000, well above 0 for stddev).
    for i in range(21, 41):
        logic.on_daily_bar(_bar("X", low=99.9, close=100.0, volume=1_000.0, day_offset=i))
    # Bar 41: second Day-1 trigger fires (rolling window has fully evicted the prior trigger bar).
    second = logic.on_daily_bar(_bar("X", low=99.5, close=99.5, volume=3_000.0, day_offset=41))
    assert isinstance(second, SetupDetected)
    assert second.day1_close == 99.5
