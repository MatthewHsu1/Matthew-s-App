from __future__ import annotations

from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.max_position import make_max_position_check


def _probe(qty=10, px=100.0, side="BUY"):
    return OrderProbe(instrument_id="MSFT.NASDAQ", side=side, quantity=qty, limit_price=px)


def test_allows_below_cap():
    check = make_max_position_check(max_usd=5000.0)
    ctx = RiskContext(positions_usd={"MSFT.NASDAQ": 1000.0})
    d = check(_probe(qty=10, px=100.0), ctx)
    assert d.allowed


def test_blocks_when_buy_would_exceed_cap():
    check = make_max_position_check(max_usd=1500.0)
    ctx = RiskContext(positions_usd={"MSFT.NASDAQ": 1000.0})
    d = check(_probe(qty=10, px=100.0), ctx)
    assert not d.allowed
    assert "max_position" in d.reason


def test_sell_reducing_position_always_allowed():
    check = make_max_position_check(max_usd=500.0)
    ctx = RiskContext(positions_usd={"MSFT.NASDAQ": 2000.0})
    d = check(_probe(qty=5, px=100.0, side="SELL"), ctx)
    assert d.allowed
