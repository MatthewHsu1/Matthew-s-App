"""Tests use a stub msgbus + risk_logger so we don't boot a real Nautilus kernel."""
from __future__ import annotations

from dataclasses import dataclass

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import RiskContext
from alpha_engine.risk.order_gate import AlphaOrderGate


class _FakeMsgbus:
    def __init__(self):
        self.subscriptions: list[tuple[str, object]] = []
        self.published: list[tuple[str, object]] = []

    def subscribe(self, topic, handler, **kwargs):
        self.subscriptions.append((topic, handler))

    def publish(self, topic, msg):
        self.published.append((topic, msg))


class _FakeLogger:
    def __init__(self):
        self.events: list[dict] = []

    def log_decision(self, **kwargs):
        self.events.append({"event": "decision", **kwargs})

    def log_error(self, **kwargs):
        self.events.append({"event": "error", **kwargs})


@dataclass
class _FakeCmd:
    client_order_id: str
    instrument_id: str
    side: str
    quantity: float
    limit_price: float


def _allow():
    def f(probe, ctx):
        return Decision.allow()
    f.name = "ok"
    return f


def _block(reason="bad"):
    def f(probe, ctx):
        return Decision.block(reason)
    f.name = "limiter"
    return f


def test_subscribes_to_submit_order_topic():
    bus = _FakeMsgbus()
    gate = AlphaOrderGate(
        msgbus=bus,
        risk_logger=_FakeLogger(),
        checks=[_allow()],
        context_provider=lambda: RiskContext(),
    )
    gate.on_start()
    topics = [t for t, _ in bus.subscriptions]
    assert "commands.trading.submit_order" in topics


def test_allowed_order_does_not_publish_denied():
    bus = _FakeMsgbus()
    logger = _FakeLogger()
    gate = AlphaOrderGate(
        msgbus=bus,
        risk_logger=logger,
        checks=[_allow()],
        context_provider=lambda: RiskContext(),
    )
    gate.on_start()
    _, handler = bus.subscriptions[0]
    handler(_FakeCmd("c1", "AAPL.NASDAQ", "BUY", 10, 100.0))
    denied = [m for t, m in bus.published if "denied" in t.lower()]
    assert denied == []
    assert any(e["event"] == "decision" for e in logger.events)


def test_blocked_order_publishes_denied_and_logs():
    bus = _FakeMsgbus()
    logger = _FakeLogger()
    gate = AlphaOrderGate(
        msgbus=bus,
        risk_logger=logger,
        checks=[_block("max_position exceeded")],
        context_provider=lambda: RiskContext(),
    )
    gate.on_start()
    _, handler = bus.subscriptions[0]
    handler(_FakeCmd("c2", "AAPL.NASDAQ", "BUY", 10, 100.0))
    denied = [m for t, m in bus.published if "denied" in t.lower()]
    assert len(denied) == 1
    block_decisions = [e for e in logger.events if e.get("decision") == "block"]
    assert len(block_decisions) == 1
    assert block_decisions[0]["reason"] == "max_position exceeded"
