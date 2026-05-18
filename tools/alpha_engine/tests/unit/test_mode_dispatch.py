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


def _make_cfg(*, historical_source: str = "synthetic_fixture", catalog_path: str | None = None):
    return EnvConfig(
        env_name="t",
        mode=Mode.BACKTEST,
        strategy=StrategyConfig(ref="bband_volume_setup", params={}),
        venue=VenueConfig(id="nasdaq_sim", account_kind="paper"),
        data=DataConfig(
            live_source="venue",
            historical_source=historical_source,
            instruments=("MSFT.NASDAQ",),
            bar_spec="1-DAY-LAST",
            start_date="2024-01-02",
            end_date="2024-01-10",
            catalog_path=catalog_path,
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(timezone="UTC"),
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


def test_dispatch_uses_catalog_loader_when_source_is_parquet_catalog(
    tmp_path,
) -> None:
    """When historical_source='parquet_catalog', env_start uses catalog_loader."""
    from alpha_engine.cli_commands.env_start import _resolve_data_loader_for_backtest

    cfg = _make_cfg(
        historical_source="parquet_catalog",
        catalog_path=str(tmp_path / "catalog"),
    )

    loader = _resolve_data_loader_for_backtest(cfg)

    from alpha_engine.engine.catalog_loader import build_engine_from_catalog

    assert loader is build_engine_from_catalog


def test_dispatch_rejects_alpaca_historical() -> None:
    from alpha_engine.cli_commands.env_start import _resolve_data_loader_for_backtest

    cfg = _make_cfg(historical_source="alpaca_historical")

    with pytest.raises(ValueError, match=r"alpaca_historical.*no longer supported"):
        _resolve_data_loader_for_backtest(cfg)


def test_dispatch_rejects_ibkr_historical() -> None:
    from alpha_engine.cli_commands.env_start import _resolve_data_loader_for_backtest

    cfg = _make_cfg(historical_source="ibkr_historical")

    with pytest.raises(ValueError, match=r"ibkr_historical.*no longer supported"):
        _resolve_data_loader_for_backtest(cfg)
