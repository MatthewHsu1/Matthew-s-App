"""Subscribe to Nautilus's MessageBus and collect OrderFilled events as TradeRecords.

Runner scripts construct an `OrderFillRecorder`, hand it to
`attach_order_fill_recorder(msgbus, recorder=...)`, run the backtest /
live node, and then dump `recorder.records` into `trades.parquet` via
`reporting.trades.write_trades_parquet`.

This module replaces `logging_/jsonl.py` (custom JSONL handler) — Nautilus's
own `LoggingConfig(log_file_format="json", log_directory=...)` covers
engine-level structured logging.
"""
from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.model.events import (
    OrderAccepted,
    OrderCanceled,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
)

from alpha_engine.reporting.trades import TradeRecord


class OrderFillRecorder:
    """Accumulates TradeRecords produced from OrderFilled events.

    Non-fill order events are silently dropped — we only care about
    realized trades for the report.
    """

    def __init__(self, *, env_name: str, strategy_class: str) -> None:
        self._env_name = env_name
        self._strategy_class = strategy_class
        self.records: list[TradeRecord] = []

    def handle(self, event) -> None:
        if isinstance(event, OrderFilled):
            ts = datetime.fromtimestamp(event.ts_event / 1e9, tz=timezone.utc)
            self.records.append(
                TradeRecord(
                    ts=ts,
                    env_name=self._env_name,
                    strategy_class=self._strategy_class,
                    instrument_id=str(event.instrument_id),
                    side=event.order_side.name,
                    quantity=float(event.last_qty),
                    price=float(event.last_px),
                    fees=float(getattr(event, "commission", 0.0) or 0.0),
                )
            )
            return
        if isinstance(event, (OrderSubmitted, OrderAccepted, OrderCanceled, OrderRejected)):
            return


def attach_order_fill_recorder(msgbus, *, recorder: OrderFillRecorder) -> None:
    """Subscribe `recorder.handle` to all order events on the msgbus.

    Topic `events.order.*` matches every Nautilus order-event topic of the
    form `events.order.{strategy_id}` via the MessageBus wildcard engine.
    """
    msgbus.subscribe(topic="events.order.*", handler=recorder.handle)
