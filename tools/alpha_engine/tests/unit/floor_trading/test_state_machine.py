"""Floor Trading state machine unit tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from alpha_engine.strategies.floor_trading.params import FloorTradingParams
from alpha_engine.strategies.floor_trading.state_machine import (
    FloorStateMachine,
    IntentKind,
    SymbolState,
)

_T0 = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)  # 4pm ET = daily close


def _params(**overrides) -> FloorTradingParams:
    return FloorTradingParams(**overrides)


# ---------- Task 4 transitions ----------

def test_unknown_symbol_state_is_idle() -> None:
    sm = FloorStateMachine(_params())
    assert sm.state_of("X") is SymbolState.IDLE


def test_seed_setup_from_idle_transitions_to_setup_detected() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.5, ts=_T0)
    assert sm.state_of("X") is SymbolState.SETUP_DETECTED


def test_seed_setup_is_idempotent_in_setup_detected() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.5, ts=_T0)
    sm.seed_setup(symbol="X", day1_close=101.0, day1_low=100.0, ts=_T0)
    assert sm.state_of("X") is SymbolState.SETUP_DETECTED


def test_seed_setup_noop_when_position_active() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.5, ts=_T0)
    # Force the state forward past SETUP_DETECTED to simulate a position in flight.
    sm._force_state_for_test("X", SymbolState.HOLDING_T1)
    sm.seed_setup(symbol="X", day1_close=200.0, day1_low=190.0, ts=_T0)
    assert sm.state_of("X") is SymbolState.HOLDING_T1  # unchanged


# ---------- Task 5 transitions: Day-2 entry path ----------

def test_day2_open_above_day1_close_abandons() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    # Day 2 daily bar: open >= Day 1 close => abandon.
    intent = sm.on_session_open(symbol="X", open_price=100.0, ts=_T0 + timedelta(days=1))
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.IDLE


def test_day2_open_below_day1_close_arms_pre_entry() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    intent = sm.on_session_open(symbol="X", open_price=99.5, ts=_T0 + timedelta(days=1))
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.DAY2_PRE_ENTRY


def test_day2_down_spike_fires_tranche_1() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    sm.on_session_open(symbol="X", open_price=99.5, ts=_T0 + timedelta(days=1))
    intent = sm.on_spike(
        symbol="X",
        kind_down=True,
        spike_price=98.0,
        ts=_T0 + timedelta(days=1, hours=1),
    )
    assert intent.kind is IntentKind.ENTER_TRANCHE
    assert intent.tranche_index == 1
    assert intent.symbol == "X"
    assert sm.state_of("X") is SymbolState.HOLDING_T1


def test_day2_up_spike_pre_entry_abandons() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    sm.on_session_open(symbol="X", open_price=99.5, ts=_T0 + timedelta(days=1))
    intent = sm.on_spike(
        symbol="X", kind_down=False,
        spike_price=101.0, ts=_T0 + timedelta(days=1, hours=1),
    )
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.IDLE


def test_day2_no_spike_at_session_close_abandons() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    sm.on_session_open(symbol="X", open_price=99.5, ts=_T0 + timedelta(days=1))
    intent = sm.on_session_close(
        symbol="X",
        day_close=99.0, day_open=99.5, day_high=99.6, day_low=98.5, day_volume=1_000_000.0,
        ts=_T0 + timedelta(days=1),
    )
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.IDLE


def test_t1_fill_records_fill_price() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    sm.on_session_open(symbol="X", open_price=99.5, ts=_T0 + timedelta(days=1))
    sm.on_spike(symbol="X", kind_down=True, spike_price=98.0, ts=_T0 + timedelta(days=1, hours=1))
    sm.on_t1_filled(symbol="X", fill_price=97.95, ts=_T0 + timedelta(days=1, hours=1, minutes=1))
    # Verify fill price is stored (used as stop reference in Task 7).
    assert sm._books["X"].t1_fill_price == 97.95


def test_on_t1_filled_noop_when_not_holding_t1() -> None:
    sm = FloorStateMachine(_params())
    sm.seed_setup(symbol="X", day1_close=100.0, day1_low=99.0, ts=_T0)
    # State is SETUP_DETECTED, not HOLDING_T1 -- the fill callback should be ignored.
    sm.on_t1_filled(symbol="X", fill_price=97.95, ts=_T0 + timedelta(days=1, hours=1, minutes=1))
    assert sm._books["X"].t1_fill_price == 0.0
    assert sm._books["X"].t1_fill_ts is None


# ---------- Task 6 transitions: Day-3 scaling + TP exit ----------

def _arrive_at_holding_t1(sm: FloorStateMachine, symbol: str, *, day1_close: float = 100.0, day2_close: float = 98.0) -> None:
    """Helper: drive the SM through IDLE -> SETUP_DETECTED -> DAY2_PRE_ENTRY -> HOLDING_T1.

    Records Day-2 close on session_close so Day-3 open-rule has its reference.
    """
    sm.seed_setup(symbol=symbol, day1_close=day1_close, day1_low=99.0, ts=_T0)
    sm.on_session_open(symbol=symbol, open_price=day1_close - 0.5, ts=_T0 + timedelta(days=1))
    sm.on_spike(symbol=symbol, kind_down=True, spike_price=day2_close, ts=_T0 + timedelta(days=1, hours=1))
    sm.on_t1_filled(symbol=symbol, fill_price=day2_close, ts=_T0 + timedelta(days=1, hours=1, minutes=1))
    sm.on_session_close(
        symbol=symbol, day_close=day2_close, day_open=day1_close - 0.5,
        day_high=day1_close - 0.4, day_low=day2_close - 0.2, day_volume=1_500_000.0,
        ts=_T0 + timedelta(days=1, hours=7),
    )


def test_day3_open_above_day2_close_holds_t1_only() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    intent = sm.on_session_open(symbol="X", open_price=99.0, ts=_T0 + timedelta(days=2))  # > 98 day-2 close
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.HOLDING_T1


def test_day3_open_below_day2_close_arms_pre_add() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    intent = sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))  # < 98 day-2 close
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.DAY3_PRE_ADD


def test_day3_down_spike_fires_tranche_2() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))
    intent = sm.on_spike(symbol="X", kind_down=True, spike_price=97.0, ts=_T0 + timedelta(days=2, hours=1))
    assert intent.kind is IntentKind.ENTER_TRANCHE
    assert intent.tranche_index == 2
    assert sm.state_of("X") is SymbolState.HOLDING_T1_T2


def test_day3_up_spike_takes_profit() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))
    intent = sm.on_spike(symbol="X", kind_down=False, spike_price=99.0, ts=_T0 + timedelta(days=2, hours=2))
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "take_profit"
    assert sm.state_of("X") is SymbolState.EXITED


def test_day3_no_spike_holds_t1_into_day4() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))
    # No spike fires all day; session close fires.
    intent = sm.on_session_close(
        symbol="X", day_close=97.5, day_open=97.5,
        day_high=97.6, day_low=97.0, day_volume=1_200_000.0,
        ts=_T0 + timedelta(days=2, hours=7),
    )
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.DAY4_HOLDING


def test_day3_up_spike_in_holding_t1_without_pre_add_also_exits() -> None:
    # Day-3 open >= Day-2 close => HOLDING_T1 (no pre-add). Up-spike still exits.
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_session_open(symbol="X", open_price=99.0, ts=_T0 + timedelta(days=2))  # holds t1
    intent = sm.on_spike(symbol="X", kind_down=False, spike_price=101.0, ts=_T0 + timedelta(days=2, hours=2))
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "take_profit"
    assert sm.state_of("X") is SymbolState.EXITED


# ---------- Task 7 transitions: stop-loss + Day-4 default close + re-arm ----------

def test_stop_fires_when_print_below_threshold() -> None:
    sm = FloorStateMachine(_params())  # stop_pct_below_t1 = 1.5
    _arrive_at_holding_t1(sm, "X")
    # T1 fill = 98.0; stop = 98 * (1 - 0.015) = 96.53
    intent = sm.on_print_for_stop(symbol="X", print_price=96.5, ts=_T0 + timedelta(days=2, hours=1))
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "stop_loss"
    assert sm.state_of("X") is SymbolState.EXITED


def test_stop_does_not_fire_above_threshold() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    intent = sm.on_print_for_stop(symbol="X", print_price=96.6, ts=_T0 + timedelta(days=2, hours=1))
    assert intent.kind is IntentKind.NO_OP
    assert sm.state_of("X") is SymbolState.HOLDING_T1


def test_stop_inclusive_at_exact_threshold() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    # T1 fill = 98.0; threshold = 98 * (1 - 0.015) = 96.53
    intent = sm.on_print_for_stop(symbol="X", print_price=96.53, ts=_T0 + timedelta(days=2, hours=1))
    assert intent.kind is IntentKind.EXIT_ALL


def test_stop_priority_over_tp_same_print() -> None:
    # Stop fires first via on_print_for_stop, then any subsequent spike on EXITED is no-op.
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))
    stop_intent = sm.on_print_for_stop(symbol="X", print_price=96.0, ts=_T0 + timedelta(days=2, hours=1))
    assert stop_intent.kind is IntentKind.EXIT_ALL
    spike_intent = sm.on_spike(symbol="X", kind_down=False, spike_price=99.0, ts=_T0 + timedelta(days=2, hours=1, seconds=1))
    assert spike_intent.kind is IntentKind.NO_OP


def _arrive_at_day4(sm: FloorStateMachine, symbol: str) -> None:
    """Drive SM through to Day-4 HOLDING (no T2 added, no exits)."""
    _arrive_at_holding_t1(sm, symbol)
    # Day-3 opens above Day-2 close -> no T2 add. Day-3 session-close advances days_held.
    sm.on_session_open(symbol=symbol, open_price=99.0, ts=_T0 + timedelta(days=2))
    sm.on_session_close(
        symbol=symbol, day_close=98.5, day_open=99.0,
        day_high=99.0, day_low=98.0, day_volume=1_000_000.0,
        ts=_T0 + timedelta(days=2, hours=7),
    )


def test_day4_default_close_exits_at_session_close() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_day4(sm, "X")
    assert sm.state_of("X") is SymbolState.DAY4_HOLDING
    intent = sm.on_session_close(
        symbol="X", day_close=98.7, day_open=98.5,
        day_high=98.8, day_low=98.0, day_volume=900_000.0,
        ts=_T0 + timedelta(days=3, hours=7),
    )
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "default_close"
    assert sm.state_of("X") is SymbolState.EXITED


def test_re_arm_after_exited_back_to_idle_on_next_seed() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    sm.on_print_for_stop(symbol="X", print_price=96.0, ts=_T0 + timedelta(days=2, hours=1))
    assert sm.state_of("X") is SymbolState.EXITED
    # New Day-1 setup on the same symbol after exit should re-arm.
    sm.on_setup_complete(symbol="X")  # explicit reset hook called by wrapper after EXIT_ALL filled
    sm.seed_setup(symbol="X", day1_close=110.0, day1_low=109.0, ts=_T0 + timedelta(days=5))
    assert sm.state_of("X") is SymbolState.SETUP_DETECTED


def test_day4_holding_up_spike_takes_profit() -> None:
    # DAY4_HOLDING + up-spike should also exit on TP (same as HOLDING_T1/HOLDING_T1_T2).
    sm = FloorStateMachine(_params())
    _arrive_at_day4(sm, "X")
    intent = sm.on_spike(symbol="X", kind_down=False, spike_price=99.5, ts=_T0 + timedelta(days=3, hours=1))
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "take_profit"
    assert sm.state_of("X") is SymbolState.EXITED


def test_day4_holding_stop_fires() -> None:
    # DAY4_HOLDING + stop-trigger print should also fire stop.
    sm = FloorStateMachine(_params())
    _arrive_at_day4(sm, "X")
    intent = sm.on_print_for_stop(symbol="X", print_price=96.0, ts=_T0 + timedelta(days=3, hours=1))
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "stop_loss"
    assert sm.state_of("X") is SymbolState.EXITED


def test_stop_fires_from_day3_pre_add() -> None:
    sm = FloorStateMachine(_params())
    _arrive_at_holding_t1(sm, "X")
    # Day-3 opens below Day-2 close -> arms DAY3_PRE_ADD.
    sm.on_session_open(symbol="X", open_price=97.5, ts=_T0 + timedelta(days=2))
    assert sm.state_of("X") is SymbolState.DAY3_PRE_ADD
    # Stop fires before any spike could classify.
    intent = sm.on_print_for_stop(
        symbol="X",
        print_price=96.0,  # below T1 fill (98.0) * 0.985 = 96.53
        ts=_T0 + timedelta(days=2, hours=1),
    )
    assert intent.kind is IntentKind.EXIT_ALL
    assert intent.reason == "stop_loss"
    assert sm.state_of("X") is SymbolState.EXITED
