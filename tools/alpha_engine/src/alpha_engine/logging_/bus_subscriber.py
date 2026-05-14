from __future__ import annotations

import logging
from pathlib import Path

from nautilus_trader.model.events import (
    OrderAccepted,
    OrderCanceled,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
)

from alpha_engine.logging_.events import (
    ORDER_ACKED,
    ORDER_CANCELED,
    ORDER_FILLED,
    ORDER_REJECTED,
    ORDER_SUBMITTED,
)
from alpha_engine.logging_.jsonl import (
    PACKAGE_LOGGER_NAME,
    JsonlHandler,
    _StaticContextFilter,
)


def attach_order_logger_to_msgbus(
    msgbus,
    *,
    path: Path,
    run_id: str,
    env_name: str,
    mode: str,
) -> JsonlHandler:
    """Subscribe a dedicated logger to Nautilus's MessageBus for order events.

    Writes to a separate JSONL file from engine.jsonl so the order journal stays
    grep-clean. Returns the handler so the engine can flush/detach on shutdown.

    In Nautilus 1.226.0 order events are published on topics of the form
    ``events.order.{strategy_id}``. The wildcard ``events.order.*`` matches all
    strategy-specific topics via the MessageBus wildcard engine.
    """
    handler = JsonlHandler(path=Path(path))
    handler.addFilter(_StaticContextFilter(run_id=run_id, env_name=env_name, mode=mode))
    logger = logging.getLogger(f"{PACKAGE_LOGGER_NAME}.orders")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # do not duplicate into engine.jsonl

    def _on_event(event_name: str, payload: dict) -> None:
        logger.info(event_name, extra=payload)

    msgbus.subscribe(
        topic="events.order.*",
        handler=lambda evt: _dispatch(evt, _on_event),
    )
    return handler


def _dispatch(evt, on_event) -> None:
    if isinstance(evt, OrderSubmitted):
        on_event(ORDER_SUBMITTED, {"client_order_id": str(evt.client_order_id)})
    elif isinstance(evt, OrderAccepted):
        on_event(ORDER_ACKED, {"client_order_id": str(evt.client_order_id)})
    elif isinstance(evt, OrderFilled):
        on_event(
            ORDER_FILLED,
            {
                "client_order_id": str(evt.client_order_id),
                "instrument_id": str(evt.instrument_id),
                "side": evt.order_side.name,
                "quantity": float(evt.last_qty),
                "price": float(evt.last_px),
            },
        )
    elif isinstance(evt, OrderCanceled):
        on_event(ORDER_CANCELED, {"client_order_id": str(evt.client_order_id)})
    elif isinstance(evt, OrderRejected):
        on_event(
            ORDER_REJECTED,
            {"client_order_id": str(evt.client_order_id), "reason": str(evt.reason)},
        )
