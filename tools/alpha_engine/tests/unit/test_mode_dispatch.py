from __future__ import annotations

import pytest

from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.engine.boot import dispatch_mode


def _cfg(mode):
    return EnvConfig(
        env_name="e",
        mode=mode,
        strategy=StrategyConfig(ref="toy_buy_and_hold"),
        venue=VenueConfig(id="ibkr", account_kind="paper"),
        data=DataConfig(
            live_source="ibkr",
            historical_source="synthetic_fixture",
            instruments=("AAPL.NASDAQ",),
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(),
    )


def test_backtest_routes_to_run_backtest():
    fn = dispatch_mode(_cfg(Mode.BACKTEST))
    assert fn.__name__ == "run_backtest"


def test_paper_routes_to_run_paper():
    fn = dispatch_mode(_cfg(Mode.PAPER))
    assert fn.__name__ == "run_paper"


def test_live_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Phase 3"):
        dispatch_mode(_cfg(Mode.LIVE))
