from __future__ import annotations

from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.price_band import make_price_band_check


def _probe(px):
    return OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=1, limit_price=px)


def test_allows_within_band():
    check = make_price_band_check(max_bps=50)
    ctx = RiskContext(last_quote={"MSFT.NASDAQ": 100.0})
    assert check(_probe(100.4), ctx).allowed


def test_blocks_above_band():
    check = make_price_band_check(max_bps=50)
    ctx = RiskContext(last_quote={"MSFT.NASDAQ": 100.0})
    d = check(_probe(101.0), ctx)
    assert not d.allowed
    assert "price_band" in d.reason


def test_market_order_with_no_limit_is_allowed():
    check = make_price_band_check(max_bps=50)
    ctx = RiskContext(last_quote={"MSFT.NASDAQ": 100.0})
    probe = OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=1, limit_price=None)
    assert check(probe, ctx).allowed


def test_blocks_when_no_quote_and_limit_given():
    check = make_price_band_check(max_bps=50)
    ctx = RiskContext(last_quote={})
    d = check(_probe(100.0), ctx)
    assert not d.allowed
    assert "no_quote" in d.reason
