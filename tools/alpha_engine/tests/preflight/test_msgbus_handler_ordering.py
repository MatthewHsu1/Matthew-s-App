"""Pre-flight: verify msgbus dispatch ordering allows the OrderGate to intercept
SubmitOrder commands before the RiskEngine processes them.

If this test fails, the OrderGate design (compose) cannot work as specified.
Pivot decision required — see spec §3 decision #4. STOP and surface.
"""
from __future__ import annotations

import pytest

from nautilus_trader.common.component import MessageBus, TestClock
from nautilus_trader.model.identifiers import TraderId


def test_higher_priority_handler_fires_first():
    """If MessageBus.subscribe supports priority, higher priority fires first.

    Document the exact behavior of the installed version. The OrderGate
    will be wired against whatever this test confirms.
    """
    clock = TestClock()
    bus = MessageBus(trader_id=TraderId("TESTER-001"), clock=clock)

    received: list[str] = []

    def low_priority_handler(msg):
        received.append("low")

    def high_priority_handler(msg):
        received.append("high")

    # If your installed Nautilus supports priority, uncomment the kwarg.
    # Otherwise fall back to subscription-order semantics and document.
    try:
        bus.subscribe(topic="test.topic", handler=high_priority_handler, priority=10)
        bus.subscribe(topic="test.topic", handler=low_priority_handler, priority=1)
        priority_supported = True
    except TypeError:
        bus.subscribe(topic="test.topic", handler=high_priority_handler)
        bus.subscribe(topic="test.topic", handler=low_priority_handler)
        priority_supported = False

    bus.publish(topic="test.topic", msg="ping")

    if priority_supported:
        assert received == ["high", "low"], (
            f"Priority subscribe is supported but dispatch order is {received}. "
            "OrderGate cannot rely on priority — pivot required."
        )
    else:
        # Without priority, the OrderGate must register BEFORE the RiskEngine
        # (i.e. earlier subscription wins). Document this guarantee:
        assert received == ["high", "low"], (
            "Without priority kwarg, msgbus must dispatch in subscription order. "
            f"Actual: {received}. OrderGate strategy needs to change."
        )


def test_handler_can_be_a_method_on_an_actor_subclass():
    """The OrderGate is an Actor subclass; verify subscribing a bound method works."""
    clock = TestClock()
    bus = MessageBus(trader_id=TraderId("TESTER-001"), clock=clock)

    class Gate:
        def __init__(self):
            self.seen = []

        def on_msg(self, msg):
            self.seen.append(msg)

    gate = Gate()
    bus.subscribe(topic="commands.trading.submit_order", handler=gate.on_msg)
    bus.publish(topic="commands.trading.submit_order", msg="fake_cmd")
    assert gate.seen == ["fake_cmd"]
