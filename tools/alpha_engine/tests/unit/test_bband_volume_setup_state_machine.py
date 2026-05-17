"""Unit tests for the BBand+Volume setup strategy's pure state machine.

The state machine is Nautilus-free so it can be exercised quickly with
synthetic OHLCV input. Each test feeds a deterministic bar sequence and
asserts the emitted intent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from alpha_engine.strategies.bband_volume_setup.state_machine import (
    BBandVolumeSetupParams,
    BBandVolumeSetupStateMachine,
    DailyBar,
    Intent,
    IntentKind,
    MinuteBar,
    SymbolState,
)


def _params(**overrides) -> BBandVolumeSetupParams:
    base = dict(
        bband_period=20,
        bband_stddev=2.0,
        volume_avg_period=20,
        day1_volume_multiplier=2.0,
        spike_volume_multiplier=3.0,
        spike_price_move_pct=1.5,
        surge_volume_multiplier=2.0,
        surge_requires_price_below_open=True,
        surge_min_gap_minutes=30,
        tranche_count=3,
        hard_stop_pct_below_day1_low=2.0,
        max_hold_days=5,
    )
    base.update(overrides)
    return BBandVolumeSetupParams(**base)


def _flat_history(symbol: str, n: int, price: float, volume: float) -> list[DailyBar]:
    """n bars of identical OHLCV. Used to seed the rolling windows."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        DailyBar(
            symbol=symbol,
            ts=start + timedelta(days=i),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
        )
        for i in range(n)
    ]


class TestDay1SetupDetection:
    def test_no_intent_while_history_window_unfilled(self) -> None:
        sm = BBandVolumeSetupStateMachine(_params())
        for bar in _flat_history("AAPL", 5, price=100.0, volume=1_000_000):
            assert sm.on_daily_bar(bar).kind is IntentKind.NO_OP

    def test_no_setup_when_volume_normal_and_price_inside_band(self) -> None:
        sm = BBandVolumeSetupStateMachine(_params())
        for bar in _flat_history("AAPL", 20, price=100.0, volume=1_000_000):
            sm.on_daily_bar(bar)
        normal = DailyBar(
            symbol="AAPL",
            ts=datetime(2026, 1, 21, tzinfo=timezone.utc),
            open=100.0,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=1_000_000,  # 1x avg, not 2x
        )
        intent = sm.on_daily_bar(normal)
        assert intent.kind is IntentKind.NO_OP
        assert sm.state_of("AAPL") is SymbolState.IDLE

    def test_setup_detected_when_volume_2x_and_low_breaks_lower_band(self) -> None:
        sm = _setup_with_day1_triggered()
        # Day 1 itself does not enter — it sets up the watch for Day 2.
        assert sm.state_of("AAPL") is SymbolState.SETUP_DETECTED


def _build_history(symbol: str = "AAPL") -> tuple[BBandVolumeSetupStateMachine, datetime]:
    """20-bar alternating-price history that yields a non-degenerate BBand."""
    sm = BBandVolumeSetupStateMachine(_params())
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(20):
        px = 100.0 + (1.5 if i % 2 == 0 else -1.5)
        sm.on_daily_bar(
            DailyBar(
                symbol=symbol, ts=start + timedelta(days=i),
                open=px, high=px + 0.5, low=px - 0.5, close=px,
                volume=1_000_000,
            )
        )
    return sm, start


def _setup_with_day1_triggered(symbol: str = "AAPL") -> BBandVolumeSetupStateMachine:
    sm, start = _build_history(symbol)
    day1 = DailyBar(
        symbol=symbol, ts=start + timedelta(days=20),
        open=99.0, high=99.5, low=96.0, close=97.5,  # low pierces lower band ≈ 97
        volume=2_500_000,                             # 2.5x avg
    )
    sm.on_daily_bar(day1)
    return sm


class TestDay2Entry:
    def test_day2_green_open_emits_first_tranche_entry(self) -> None:
        sm = _setup_with_day1_triggered()
        # Day 1 close was 97.5. A green open means open > prior close.
        day2 = DailyBar(
            symbol="AAPL",
            ts=datetime(2026, 1, 22, tzinfo=timezone.utc),
            open=98.0, high=98.0, low=98.0, close=98.0,
            volume=1_000_000,
        )
        intent = sm.on_daily_bar(day2)
        assert intent.kind is IntentKind.ENTER_TRANCHE
        assert intent.symbol == "AAPL"
        assert intent.tranche_index == 1
        assert sm.state_of("AAPL") is SymbolState.DAY2_ACTIVE

    def test_day2_red_open_invalidates_setup_back_to_idle(self) -> None:
        sm = _setup_with_day1_triggered()
        # Open <= prior close — red. Setup is invalidated.
        day2 = DailyBar(
            symbol="AAPL",
            ts=datetime(2026, 1, 22, tzinfo=timezone.utc),
            open=97.0, high=97.0, low=97.0, close=97.0,
            volume=1_000_000,
        )
        intent = sm.on_daily_bar(day2)
        assert intent.kind is IntentKind.NO_OP
        assert sm.state_of("AAPL") is SymbolState.IDLE


def _advance_to_day2_active(symbol: str = "AAPL") -> tuple[BBandVolumeSetupStateMachine, datetime]:
    sm = _setup_with_day1_triggered(symbol)
    day2_ts = datetime(2026, 1, 22, 9, 30, tzinfo=timezone.utc)
    sm.on_daily_bar(
        DailyBar(
            symbol=symbol, ts=day2_ts,
            open=98.0, high=98.0, low=98.0, close=98.0,
            volume=1_000_000,
        )
    )
    return sm, day2_ts


def _fill_minute_baseline(
    sm: BBandVolumeSetupStateMachine,
    symbol: str,
    start_ts: datetime,
    volume: float = 10_000,
    price: float = 98.0,
) -> datetime:
    """Feed 20 quiet 5-min bars to seed the minute rolling avg."""
    ts = start_ts
    for _ in range(20):
        sm.on_minute_bar(
            MinuteBar(
                symbol=symbol, ts=ts,
                open=price, high=price, low=price, close=price,
                volume=volume,
            )
        )
        ts += timedelta(minutes=5)
    return ts


class TestDay2SpikeExit:
    def test_spike_exits_all_and_marks_exited(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        after = _fill_minute_baseline(sm, "AAPL", day2_ts + timedelta(minutes=5))
        # Spike: 3x volume AND price 2% above day's open (98 → 100).
        spike = MinuteBar(
            symbol="AAPL", ts=after,
            open=99.0, high=100.0, low=99.0, close=100.0,
            volume=40_000,  # 4x quiet baseline
        )
        intent = sm.on_minute_bar(spike)
        assert intent.kind is IntentKind.EXIT_ALL
        assert intent.symbol == "AAPL"
        assert sm.state_of("AAPL") is SymbolState.EXITED

    def test_high_volume_without_price_move_is_not_a_spike(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        after = _fill_minute_baseline(sm, "AAPL", day2_ts + timedelta(minutes=5))
        churn = MinuteBar(
            symbol="AAPL", ts=after,
            open=98.0, high=98.3, low=97.7, close=98.0,  # +0% from day open
            volume=40_000,
        )
        intent = sm.on_minute_bar(churn)
        assert intent.kind is IntentKind.NO_OP
        assert sm.state_of("AAPL") is SymbolState.DAY2_ACTIVE


class TestDay3Scaling:
    def test_first_surge_enters_tranche_two(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        # Close out Day 2 quietly (no spike) by feeding a new daily bar.
        day3_open_ts = day2_ts + timedelta(days=1)
        sm.on_daily_bar(
            DailyBar(
                symbol="AAPL", ts=day3_open_ts,
                open=97.5, high=97.5, low=97.5, close=97.5,
                volume=1_000_000,
            )
        )
        assert sm.state_of("AAPL") is SymbolState.DAY3_SCALING

        after = _fill_minute_baseline(sm, "AAPL", day3_open_ts + timedelta(minutes=5))
        # Surge: 2x volume, price BELOW Day 3 open (continues to fall).
        surge = MinuteBar(
            symbol="AAPL", ts=after,
            open=97.0, high=97.0, low=96.5, close=96.8,
            volume=25_000,  # 2.5x baseline
        )
        intent = sm.on_minute_bar(surge)
        assert intent.kind is IntentKind.ENTER_TRANCHE
        assert intent.tranche_index == 2

    def test_second_surge_after_gap_enters_tranche_three(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        day3_ts = day2_ts + timedelta(days=1)
        sm.on_daily_bar(
            DailyBar(
                symbol="AAPL", ts=day3_ts,
                open=97.5, high=97.5, low=97.5, close=97.5,
                volume=1_000_000,
            )
        )
        after = _fill_minute_baseline(sm, "AAPL", day3_ts + timedelta(minutes=5))
        # First surge → tranche 2.
        sm.on_minute_bar(
            MinuteBar(
                symbol="AAPL", ts=after,
                open=97.0, high=97.0, low=96.5, close=96.8,
                volume=25_000,
            )
        )
        # Same-minute follow-up volume must NOT count as tranche 3.
        immediate_follow = sm.on_minute_bar(
            MinuteBar(
                symbol="AAPL", ts=after + timedelta(minutes=5),
                open=96.8, high=96.9, low=96.5, close=96.6,
                volume=25_000,
            )
        )
        assert immediate_follow.kind is IntentKind.NO_OP

        # Second surge after the 30-min gap → tranche 3.
        gapped = sm.on_minute_bar(
            MinuteBar(
                symbol="AAPL", ts=after + timedelta(minutes=35),
                open=96.6, high=96.7, low=96.2, close=96.3,
                volume=25_000,
            )
        )
        assert gapped.kind is IntentKind.ENTER_TRANCHE
        assert gapped.tranche_index == 3


class TestExits:
    def test_hard_stop_breaks_day1_low(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        after = _fill_minute_baseline(sm, "AAPL", day2_ts + timedelta(minutes=5))
        # Day 1 low was 96. Hard stop = 2% below = 94.08.
        crash = MinuteBar(
            symbol="AAPL", ts=after,
            open=96.0, high=96.0, low=94.0, close=94.0,
            volume=10_000,
        )
        intent = sm.on_minute_bar(crash)
        assert intent.kind is IntentKind.EXIT_ALL
        assert "hard_stop" in intent.reason
        assert sm.state_of("AAPL") is SymbolState.EXITED

    def test_day5_session_exits_all_at_close(self) -> None:
        sm, day2_ts = _advance_to_day2_active()
        # Days 3, 4, 5 — feed daily bars; each new daily bar advances the day.
        ts = day2_ts
        for offset in (1, 2, 3):
            ts = day2_ts + timedelta(days=offset)
            sm.on_daily_bar(
                DailyBar(
                    symbol="AAPL", ts=ts,
                    open=97.5, high=97.5, low=97.5, close=97.5,
                    volume=1_000_000,
                )
            )
        assert sm.state_of("AAPL") is SymbolState.DAY5_FINAL
        # Day 5's session close emits the exit.
        intent = sm.on_session_close("AAPL")
        assert intent.kind is IntentKind.EXIT_ALL
        assert "max_hold" in intent.reason
        assert sm.state_of("AAPL") is SymbolState.EXITED

    def test_day6_bar_after_day5_exits_via_max_hold(self) -> None:
        """Nautilus has no explicit session-close event, so the next daily bar
        after DAY5_FINAL acts as the session-end trigger."""
        sm, day2_ts = _advance_to_day2_active()
        for offset in (1, 2, 3):
            sm.on_daily_bar(
                DailyBar(
                    symbol="AAPL", ts=day2_ts + timedelta(days=offset),
                    open=97.5, high=97.5, low=97.5, close=97.5,
                    volume=1_000_000,
                )
            )
        assert sm.state_of("AAPL") is SymbolState.DAY5_FINAL

        day6 = DailyBar(
            symbol="AAPL", ts=day2_ts + timedelta(days=4),
            open=97.5, high=97.5, low=97.5, close=97.5,
            volume=1_000_000,
        )
        intent = sm.on_daily_bar(day6)
        assert intent.kind is IntentKind.EXIT_ALL
        assert "max_hold" in intent.reason
        assert sm.state_of("AAPL") is SymbolState.EXITED
