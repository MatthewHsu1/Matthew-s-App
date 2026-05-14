from __future__ import annotations

from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.market_hours import make_market_hours_check


def _probe():
    return OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=1, limit_price=100.0)


def test_allows_when_market_open():
    check = make_market_hours_check(market_hours_only=True)
    ctx = RiskContext(market_open_now=True)
    assert check(_probe(), ctx).allowed


def test_blocks_when_market_closed_and_rth_required():
    check = make_market_hours_check(market_hours_only=True)
    ctx = RiskContext(market_open_now=False)
    d = check(_probe(), ctx)
    assert not d.allowed
    assert "market_closed" in d.reason


def test_allows_when_market_closed_and_rth_not_required():
    check = make_market_hours_check(market_hours_only=False)
    ctx = RiskContext(market_open_now=False)
    assert check(_probe(), ctx).allowed
