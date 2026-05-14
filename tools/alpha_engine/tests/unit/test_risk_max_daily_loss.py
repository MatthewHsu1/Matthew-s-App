from __future__ import annotations

from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.max_daily_loss import make_max_daily_loss_check


def _probe():
    return OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=1, limit_price=100.0)


def test_allows_when_loss_below_cap():
    check = make_max_daily_loss_check(max_loss_usd=500.0)
    ctx = RiskContext(realized_pnl_usd_today=-100.0, unrealized_pnl_usd=-50.0)
    assert check(_probe(), ctx).allowed


def test_blocks_when_combined_loss_exceeds_cap():
    check = make_max_daily_loss_check(max_loss_usd=500.0)
    ctx = RiskContext(realized_pnl_usd_today=-400.0, unrealized_pnl_usd=-150.0)
    d = check(_probe(), ctx)
    assert not d.allowed
    assert "max_daily_loss" in d.reason


def test_gain_never_blocks():
    check = make_max_daily_loss_check(max_loss_usd=500.0)
    ctx = RiskContext(realized_pnl_usd_today=1000.0, unrealized_pnl_usd=200.0)
    assert check(_probe(), ctx).allowed
