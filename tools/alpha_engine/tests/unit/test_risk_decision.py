from __future__ import annotations

from alpha_engine.contracts.decision import Decision


def test_decision_allow():
    d = Decision.allow()
    assert d.allowed is True
    assert d.reason is None


def test_decision_block_with_reason():
    d = Decision.block("max_position exceeded")
    assert d.allowed is False
    assert d.reason == "max_position exceeded"


def test_decision_is_frozen():
    import dataclasses

    d = Decision.allow()
    assert dataclasses.is_dataclass(d)
    try:
        d.allowed = False
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("Decision must be frozen")


def test_decision_block_requires_reason():
    import pytest

    with pytest.raises(ValueError):
        Decision.block("")


def test_pretrade_context_dataclass():
    from alpha_engine.risk.check import OrderProbe, RiskContext

    probe = OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=10, limit_price=100.0)
    ctx = RiskContext(
        positions_usd={"MSFT.NASDAQ": 0.0},
        last_quote={"MSFT.NASDAQ": 100.0},
        realized_pnl_usd_today=0.0,
        unrealized_pnl_usd=0.0,
        now_local=None,
        market_open_now=True,
    )
    assert probe.notional_usd() == 1000.0
    assert ctx.position_usd("MSFT.NASDAQ") == 0.0
