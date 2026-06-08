"""Tests for the thinned bus_subscriber — OrderFilled → TradeRecord recorder."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from alpha_engine.logging_.bus_subscriber import (
    OrderFillRecorder,
    attach_order_fill_recorder,
)
from alpha_engine.reporting.trades import TradeRecord


class _FakeMsgbus:
    def __init__(self) -> None:
        self.subscriptions: list[tuple[str, object]] = []

    def subscribe(self, *, topic: str, handler) -> None:
        self.subscriptions.append((topic, handler))


def _make_fill_event():
    evt = MagicMock()
    evt.ts_event = int(datetime(2026, 5, 18, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)
    evt.client_order_id = "C-1"
    evt.instrument_id = "MSFT.NASDAQ"
    evt.order_side = MagicMock(name="OrderSide.BUY")
    evt.order_side.name = "BUY"
    evt.last_qty = 10
    evt.last_px = 123.45
    evt.commission = 0.01
    return evt


def test_recorder_starts_empty():
    recorder = OrderFillRecorder(env_name="bband_v1", strategy_class="BBandVolumeSetupStrategy")
    assert recorder.records == []


def test_attach_subscribes_to_order_wildcard():
    msgbus = _FakeMsgbus()
    recorder = OrderFillRecorder(env_name="bband_v1", strategy_class="X")
    attach_order_fill_recorder(msgbus, recorder=recorder)
    assert len(msgbus.subscriptions) == 1
    assert msgbus.subscriptions[0][0] == "events.order.*"


def test_order_filled_event_appends_trade_record(monkeypatch):
    # Patch OrderFilled at the import site so isinstance() routes the dispatch.
    from alpha_engine.logging_ import bus_subscriber

    fake = _make_fill_event()
    fake.__class__ = bus_subscriber.OrderFilled  # make isinstance() succeed

    recorder = OrderFillRecorder(env_name="bband_v1", strategy_class="BBandVolumeSetupStrategy")
    msgbus = _FakeMsgbus()
    attach_order_fill_recorder(msgbus, recorder=recorder)

    handler = msgbus.subscriptions[0][1]
    handler(fake)

    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert isinstance(rec, TradeRecord)
    assert rec.instrument_id == "MSFT.NASDAQ"
    assert rec.side == "BUY"
    assert rec.quantity == 10.0
    assert rec.price == 123.45
    assert rec.fees == 0.01
    assert rec.env_name == "bband_v1"
    assert rec.strategy_class == "BBandVolumeSetupStrategy"


def test_non_fill_events_are_ignored():
    from alpha_engine.logging_ import bus_subscriber

    submitted = MagicMock()
    submitted.__class__ = bus_subscriber.OrderSubmitted
    submitted.client_order_id = "C-2"

    recorder = OrderFillRecorder(env_name="bband_v1", strategy_class="X")
    msgbus = _FakeMsgbus()
    attach_order_fill_recorder(msgbus, recorder=recorder)

    handler = msgbus.subscriptions[0][1]
    handler(submitted)

    assert recorder.records == []
