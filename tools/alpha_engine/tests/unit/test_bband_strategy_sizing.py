"""Strategy sizing + inline risk guards.

Three guards live inside `_size_tranche` / `_submit`:
  * dollar-tranche sizing (TRANCHE_DOLLARS / price, min 1 share)
  * penny-stock floor (price < min_price_usd → reject)
  * price-band reject (|est_fill - last_daily_close| / last_daily_close > pct)

EXIT_ALL must not be affected — it always submits the held quantity.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from nautilus_trader.model.enums import OrderSide

from alpha_engine.strategies.bband_volume_setup.state_machine import (
    Intent,
    IntentKind,
)
from alpha_engine.strategies.bband_volume_setup.strategy import (
    BBandVolumeSetupNautilusParams,
    BBandVolumeSetupStrategy,
)


@pytest.fixture
def strategy() -> BBandVolumeSetupStrategy:
    cfg = BBandVolumeSetupNautilusParams(
        instrument_ids=["AAPL.NASDAQ"],
        tranche_dollars=3000.0,
        min_price_usd=10.0,
        price_band_pct=5.0,
        minute_bar_step=5,
    )
    inst = BBandVolumeSetupStrategy(cfg)
    # msgbus, order_factory, and log are Cython-sealed on Actor/Strategy —
    # not writable from Python. Inject via seams added in strategy.py instead.
    inst._fake_subscribe = MagicMock()
    inst.subscribe_bars = inst._fake_subscribe  # type: ignore[assignment]
    inst._fake_unsubscribe = MagicMock()
    inst.unsubscribe_bars = inst._fake_unsubscribe  # type: ignore[assignment]
    # Seam for order_factory.market (Cython-sealed).
    inst._fake_market_order = MagicMock()
    inst._make_market_order = inst._fake_market_order  # type: ignore[method-assign]
    inst._fake_submit = MagicMock()
    inst.submit_order = inst._fake_submit  # type: ignore[assignment]
    # Seam for log.warning (Cython-sealed).
    inst._emit_warning = MagicMock()  # type: ignore[method-assign]
    return inst


def test_dollar_tranche_sizes_to_floor_of_dollars_over_price(strategy) -> None:
    strategy._last_minute_close["AAPL.NASDAQ"] = 100.0
    strategy._last_daily_close["AAPL.NASDAQ"] = 100.0
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol="AAPL.NASDAQ", tranche_index=1)
    strategy._apply_intent(intent, "AAPL.NASDAQ")

    strategy._fake_market_order.assert_called_once()
    qty_arg = strategy._fake_market_order.call_args.kwargs["quantity"]
    assert int(qty_arg.as_double()) == 30  # 3000 / 100 = 30
    assert strategy._fake_market_order.call_args.kwargs["order_side"] is OrderSide.BUY


def test_penny_stock_rejects_with_no_order_submitted(strategy) -> None:
    strategy._last_minute_close["AAPL.NASDAQ"] = 5.0  # below $10 floor
    strategy._last_daily_close["AAPL.NASDAQ"] = 5.0
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol="AAPL.NASDAQ", tranche_index=1)
    strategy._apply_intent(intent, "AAPL.NASDAQ")

    strategy._fake_market_order.assert_not_called()
    strategy._fake_submit.assert_not_called()
    assert strategy._held_qty["AAPL.NASDAQ"] == 0


def test_price_band_rejects_when_minute_close_diverges_from_daily_close(strategy) -> None:
    # 5% band on daily close 100. Minute close 110 = 10% above → reject.
    strategy._last_daily_close["AAPL.NASDAQ"] = 100.0
    strategy._last_minute_close["AAPL.NASDAQ"] = 110.0
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol="AAPL.NASDAQ", tranche_index=1)
    strategy._apply_intent(intent, "AAPL.NASDAQ")

    strategy._fake_market_order.assert_not_called()
    strategy._fake_submit.assert_not_called()


def test_price_band_within_threshold_lets_order_through(strategy) -> None:
    # 100 → 103 = 3%, under the 5% band → allowed.
    strategy._last_daily_close["AAPL.NASDAQ"] = 100.0
    strategy._last_minute_close["AAPL.NASDAQ"] = 103.0
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol="AAPL.NASDAQ", tranche_index=1)
    strategy._apply_intent(intent, "AAPL.NASDAQ")

    strategy._fake_market_order.assert_called_once()
    qty_arg = strategy._fake_market_order.call_args.kwargs["quantity"]
    assert int(qty_arg.as_double()) == 29  # int(3000 / 103) = 29


def test_exit_all_bypasses_all_guards_and_sells_held_qty(strategy) -> None:
    # Even with penny-stock + price-band conditions, EXIT_ALL must fire.
    strategy._held_qty["AAPL.NASDAQ"] = 30
    strategy._last_daily_close["AAPL.NASDAQ"] = 100.0
    strategy._last_minute_close["AAPL.NASDAQ"] = 5.0  # would fail penny guard

    intent = Intent(kind=IntentKind.EXIT_ALL, symbol="AAPL.NASDAQ", reason="hard_stop")
    strategy._apply_intent(intent, "AAPL.NASDAQ")

    strategy._fake_market_order.assert_called_once()
    assert strategy._fake_market_order.call_args.kwargs["order_side"] is OrderSide.SELL
    qty_arg = strategy._fake_market_order.call_args.kwargs["quantity"]
    assert int(qty_arg.as_double()) == 30
    assert strategy._held_qty["AAPL.NASDAQ"] == 0


def test_zero_known_price_skips_tranche_safely(strategy) -> None:
    """No daily close yet (e.g. setup just arrived, no minute bar processed) →
    we cannot size, do not submit, do not crash."""
    intent = Intent(kind=IntentKind.ENTER_TRANCHE, symbol="AAPL.NASDAQ", tranche_index=1)
    strategy._apply_intent(intent, "AAPL.NASDAQ")
    strategy._fake_market_order.assert_not_called()
