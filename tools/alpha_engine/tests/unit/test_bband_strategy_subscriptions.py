"""Strategy subscription wiring.

The new model: at on_start the strategy subscribes ONLY to the msgbus topic
`"setup.detected"`. On receipt of a payload, it seeds the state machine and
dynamically subscribes to the daily + 5-min streams for that symbol. On
EXIT_ALL the streams are unsubscribed.

We test the wiring by injecting fakes for msgbus / subscribe_bars /
unsubscribe_bars / order_factory / submit_order onto the constructed strategy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from nautilus_trader.model.enums import BarAggregation

from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC, SetupDetected
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
    # msgbus is a Cython-sealed attribute on Actor — not writable from Python.
    # We inject via the _subscribe_setup_topic seam instead (same pattern as
    # Task 5's _publish_setup seam).
    inst._fake_subscribe_topic_calls: list[tuple[str, object]] = []

    def _fake_subscribe_setup_topic(topic: str, handler) -> None:
        inst._fake_subscribe_topic_calls.append((topic, handler))

    inst._subscribe_setup_topic = _fake_subscribe_setup_topic  # type: ignore[method-assign]

    inst._fake_subscribe = MagicMock()
    inst.subscribe_bars = inst._fake_subscribe  # type: ignore[assignment]
    inst._fake_unsubscribe = MagicMock()
    inst.unsubscribe_bars = inst._fake_unsubscribe  # type: ignore[assignment]
    return inst


def test_on_start_subscribes_to_setup_detected_topic_only(strategy) -> None:
    strategy.on_start()
    assert len(strategy._fake_subscribe_topic_calls) == 1
    topic, _handler = strategy._fake_subscribe_topic_calls[0]
    assert topic == SETUP_DETECTED_TOPIC
    # No blanket subscribe_bars at startup.
    strategy._fake_subscribe.assert_not_called()


def test_on_setup_detected_subscribes_to_daily_and_minute_streams(strategy) -> None:
    strategy.on_start()
    payload = SetupDetected(
        symbol="AAPL.NASDAQ",
        ts=datetime(2026, 1, 21, tzinfo=timezone.utc),
        day1_close=97.5,
        day1_low=96.0,
    )
    strategy._on_setup_detected(payload)

    # Two subscribe_bars calls: one DAY, one 5-MINUTE.
    assert strategy._fake_subscribe.call_count == 2
    subscribed_specs = {call.args[0].spec.aggregation for call in strategy._fake_subscribe.call_args_list}
    assert subscribed_specs == {BarAggregation.DAY, BarAggregation.MINUTE}


def test_on_setup_detected_seeds_state_machine(strategy) -> None:
    from alpha_engine.strategies.bband_volume_setup.state_machine import SymbolState

    strategy.on_start()
    payload = SetupDetected(
        symbol="AAPL.NASDAQ",
        ts=datetime(2026, 1, 21, tzinfo=timezone.utc),
        day1_close=97.5,
        day1_low=96.0,
    )
    strategy._on_setup_detected(payload)
    assert strategy._state_machine.state_of("AAPL.NASDAQ") is SymbolState.SETUP_DETECTED


def test_setup_for_unknown_symbol_is_registered_dynamically(strategy) -> None:
    """The strategy starts with one configured instrument; a scan-detected
    setup for any other S&P 500 symbol must still wire up cleanly (the actor
    pre-vets membership in the universe — strategy trusts it)."""
    strategy.on_start()
    payload = SetupDetected(
        symbol="TSLA.NASDAQ",
        ts=datetime(2026, 1, 21, tzinfo=timezone.utc),
        day1_close=300.0,
        day1_low=290.0,
    )
    strategy._on_setup_detected(payload)
    assert strategy._fake_subscribe.call_count == 2  # daily + minute
    assert "TSLA.NASDAQ" in strategy._instruments
