"""Paper-boot unit tests.

These verify the boot module's public functions WITHOUT actually starting a
TradingNode (which would require Nautilus's full async runtime). The full
integration test is Task 37 (test_paper_mode_with_mock_ibkr.py).
"""
from __future__ import annotations

from alpha_engine.engine import paper as paper_mod


def test_build_pre_trade_checks_returns_four_checks():
    from alpha_engine.contracts.config import RiskConfig
    cfg = RiskConfig(
        max_position_usd=10000.0,
        max_daily_loss_usd=500.0,
        price_band_bps=200,
        market_hours_only=True,
    )
    checks = paper_mod.build_pre_trade_checks(cfg)
    names = [getattr(c, "name", c.__class__.__name__) for c in checks]
    assert "max_position" in names
    assert "max_daily_loss" in names
    assert "price_band" in names
    assert "market_hours" in names


def test_build_pre_trade_checks_skips_unset_limits():
    from alpha_engine.contracts.config import RiskConfig
    cfg = RiskConfig()  # all None
    checks = paper_mod.build_pre_trade_checks(cfg)
    assert checks == []


def test_paper_run_callable_exists():
    """run_paper exists and is callable. Full execution tested in Task 37."""
    assert callable(paper_mod.run_paper)
