"""FloorTradingStrategy wrapper tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from nautilus_trader.model.data import Bar, BarSpecification, BarType, TradeTick
from nautilus_trader.model.enums import AggregationSource, AggressorSide, BarAggregation, PriceType
from nautilus_trader.model.identifiers import InstrumentId, Symbol, TradeId, Venue
from nautilus_trader.model.objects import Price, Quantity

from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC, SetupDetected
from alpha_engine.strategies.floor_trading.state_machine import Intent, IntentKind
from alpha_engine.strategies.floor_trading.strategy import (
    FloorTradingNautilusParams,
    FloorTradingStrategy,
)

_IID = "AAPL.NASDAQ"
_T0 = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def _make_strategy(*, instrument_ids: list[str] | None = None) -> FloorTradingStrategy:
    cfg = FloorTradingNautilusParams(
        instrument_ids=instrument_ids or [_IID],
        tranche_dollars=5_000.0,
        min_price_usd=10.0,
        price_band_pct=5.0,
        max_concurrent_positions=5,
    )
    return FloorTradingStrategy(config=cfg)


def test_on_start_subscribes_to_setup_topic() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_setup_topic") as m:
        strat.on_start()
        m.assert_called_once_with(SETUP_DETECTED_TOPIC, strat._on_setup_detected)


def test_on_setup_detected_seeds_state_machine_and_subscribes_ticks() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks") as m_sub, patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(
            symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0,
        ))
        m_sub.assert_called_once()
        assert strat._state_machine.state_of(_IID).name == "SETUP_DETECTED"


# ----- Task 11: TradeTick handling -----

def _make_tick(symbol: str, venue: str, *, ts: datetime, price: float, size: int) -> TradeTick:
    return TradeTick(
        instrument_id=InstrumentId(Symbol(symbol), Venue(venue)),
        price=Price.from_str(f"{price:.2f}"),
        size=Quantity.from_int(size),
        aggressor_side=AggressorSide.NO_AGGRESSOR,
        trade_id=TradeId(f"t-{int(ts.timestamp()*1000)}"),
        ts_event=int(ts.timestamp() * 1e9),
        ts_init=int(ts.timestamp() * 1e9),
    )


def test_first_rth_tick_of_session_calls_on_session_open() -> None:
    strat = _make_strategy()
    # Seed via SetupDetected (uses Task 10's path).
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # First tick at Day 2's 9:30 EST = 14:30 UTC.
    day2_open_utc = _T0 + timedelta(days=1) - timedelta(hours=6, minutes=30)
    with patch.object(strat._state_machine, "on_session_open") as m:
        m.return_value = Intent.no_op()
        # Patch _apply_intent so a NO_OP intent doesn't cascade into other state-machine calls.
        with patch.object(strat, "_apply_intent"):
            with patch.object(strat._state_machine, "on_print_for_stop") as m_stop:
                m_stop.return_value = Intent.no_op()
                strat.on_trade_tick(_make_tick("AAPL", "NASDAQ", ts=day2_open_utc, price=99.5, size=100))
        m.assert_called_once()
        kwargs = m.call_args.kwargs
        assert kwargs["symbol"] == _IID
        assert kwargs["open_price"] == 99.5


def test_subsequent_ticks_do_not_re_call_session_open_same_day() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    day2_open_utc = _T0 + timedelta(days=1) - timedelta(hours=6, minutes=30)
    with patch.object(strat._state_machine, "on_session_open") as m_open:
        m_open.return_value = Intent.no_op()
        with patch.object(strat._state_machine, "on_print_for_stop") as m_stop:
            m_stop.return_value = Intent.no_op()
            strat.on_trade_tick(_make_tick("AAPL", "NASDAQ", ts=day2_open_utc, price=99.5, size=100))
            strat.on_trade_tick(_make_tick("AAPL", "NASDAQ", ts=day2_open_utc + timedelta(seconds=30), price=99.6, size=100))
        m_open.assert_called_once()


def test_tick_outside_rth_is_skipped() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # Pre-market tick at 13:00 UTC on Day 2 (before RTH starts at 13:30 UTC in DST window).
    pre_market = _T0 + timedelta(days=1) - timedelta(hours=8)
    with patch.object(strat._state_machine, "on_session_open") as m_open:
        with patch.object(strat._state_machine, "on_print_for_stop") as m_stop:
            strat.on_trade_tick(_make_tick("AAPL", "NASDAQ", ts=pre_market, price=99.5, size=100))
        m_open.assert_not_called()
        m_stop.assert_not_called()


def test_tick_runs_stop_check_and_submits_sell() -> None:
    from alpha_engine.strategies.floor_trading.state_machine import SymbolState
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # Force into HOLDING_T1 state with t1_fill_price = 100.0
    strat._state_machine._force_state_for_test(_IID, SymbolState.HOLDING_T1)
    strat._state_machine._books[_IID].t1_fill_price = 100.0
    strat._held_qty[_IID] = 50
    # Inject a stop-trigger tick (price <= 100 * 0.985 = 98.5).
    day2_tick_utc = _T0 + timedelta(days=1) - timedelta(hours=6, minutes=30) + timedelta(minutes=1)
    with patch.object(strat, "_submit_market_order") as m_submit:
        with patch.object(strat, "_unsubscribe_ticks"), patch.object(strat, "_unsubscribe_bars"):
            # Skip the on_session_open path by pre-marking the date.
            strat._last_session_date[_IID] = day2_tick_utc.strftime("%Y-%m-%d")
            strat.on_trade_tick(_make_tick("AAPL", "NASDAQ", ts=day2_tick_utc, price=98.0, size=100))
        m_submit.assert_called_once()
        kwargs = m_submit.call_args.kwargs
        from nautilus_trader.model.enums import OrderSide
        assert kwargs["side"] == OrderSide.SELL


def test_enter_tranche_intent_submits_buy_with_dollar_sized_qty() -> None:
    from nautilus_trader.model.enums import OrderSide

    from alpha_engine.strategies.floor_trading.state_machine import SymbolState
    strat = _make_strategy()  # tranche_dollars=5_000, min_price_usd=10
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # Force state machine into DAY2_PRE_ENTRY (post-open-rule) so spike fires entry.
    strat._state_machine._force_state_for_test(_IID, SymbolState.DAY2_PRE_ENTRY)
    # Simulate the spike-fires path by directly calling _apply_intent with ENTER_TRANCHE.
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol=_IID, tranche_index=1)
    with patch.object(strat, "_submit_market_order") as m_submit:
        strat._apply_intent(intent, _IID, current_price=100.0)
        m_submit.assert_called_once()
        kwargs = m_submit.call_args.kwargs
        assert kwargs["side"] == OrderSide.BUY
        # qty = max(1, int(5000 / 100)) = 50
        assert kwargs["qty"] == 50
        assert kwargs["symbol_id"] == _IID
    # Verify _held_qty was incremented.
    assert strat._held_qty[_IID] == 50


# ----- Task 12: daily-bar handling + Day-4 close -----

def _make_daily_bar(symbol: str, venue: str, *, ts: datetime, open_: float, high: float, low: float, close: float, volume: int) -> Bar:
    iid = InstrumentId(Symbol(symbol), Venue(venue))
    bt = BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )
    return Bar(
        bar_type=bt,
        open=Price.from_str(f"{open_:.2f}"),
        high=Price.from_str(f"{high:.2f}"),
        low=Price.from_str(f"{low:.2f}"),
        close=Price.from_str(f"{close:.2f}"),
        volume=Quantity.from_int(volume),
        ts_event=int(ts.timestamp() * 1e9),
        ts_init=int(ts.timestamp() * 1e9),
    )


def test_daily_bar_calls_state_machine_session_close() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # Day-2 close arrives.
    bar_ts = _T0 + timedelta(days=1)
    with patch.object(strat._state_machine, "on_session_close") as m:
        m.return_value = Intent.no_op()
        strat.on_bar(_make_daily_bar(
            "AAPL", "NASDAQ", ts=bar_ts,
            open_=99.5, high=99.8, low=98.5, close=99.0, volume=1_500_000,
        ))
        m.assert_called_once()
        kwargs = m.call_args.kwargs
        assert kwargs["symbol"] == _IID
        assert kwargs["day_close"] == 99.0
        assert kwargs["day_open"] == 99.5
        assert kwargs["day_high"] == 99.8
        assert kwargs["day_low"] == 98.5
        assert kwargs["day_volume"] == 1_500_000.0


def test_subscribe_daily_bars_on_setup_detected() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"):
        with patch.object(strat, "_subscribe_bars") as m_sub_bars:
            strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
            m_sub_bars.assert_called_once()
            # Subscribed bar type ends with 1-DAY-LAST-EXTERNAL.
            sub_arg = m_sub_bars.call_args.args[0]
            assert str(sub_arg).endswith("1-DAY-LAST-EXTERNAL")


def test_on_bar_ignores_non_day_aggregation() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    bar = _make_daily_bar("AAPL", "NASDAQ", ts=_T0 + timedelta(days=1),
                          open_=99.5, high=99.8, low=98.5, close=99.0, volume=1_500_000)
    # Spoof minute aggregation by recreating the bar with a minute BarType.
    iid = InstrumentId(Symbol("AAPL"), Venue("NASDAQ"))
    minute_bt = BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(5, BarAggregation.MINUTE, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )
    minute_bar = Bar(
        bar_type=minute_bt,
        open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume,
        ts_event=bar.ts_event, ts_init=bar.ts_init,
    )
    with patch.object(strat._state_machine, "on_session_close") as m:
        strat.on_bar(minute_bar)
        m.assert_not_called()


# ----- Task 12: price-band guard in _size_tranche -----

def test_size_tranche_rejects_price_band_violation() -> None:
    strat = _make_strategy()  # price_band_pct=5.0 default
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # day1_close_ref = 100.0; current_price 94.0 is 6% below, exceeding 5% band.
    qty = strat._size_tranche(_IID, current_price=94.0)
    assert qty == 0


def test_size_tranche_accepts_within_price_band() -> None:
    strat = _make_strategy()
    with patch.object(strat, "_subscribe_ticks"), patch.object(strat, "_subscribe_bars"):
        strat._on_setup_detected(SetupDetected(symbol=_IID, ts=_T0, day1_close=100.0, day1_low=99.0))
    # 4% below day1_close is within the 5% band.
    qty = strat._size_tranche(_IID, current_price=96.0)
    assert qty == max(1, int(5_000 / 96.0))  # = 52


def test_size_tranche_rejects_penny_stock() -> None:
    strat = _make_strategy()  # min_price_usd=10.0 default
    qty = strat._size_tranche(_IID, current_price=9.99)
    assert qty == 0
