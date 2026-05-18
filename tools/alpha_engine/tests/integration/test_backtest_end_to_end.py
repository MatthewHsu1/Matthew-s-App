from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import (
    DataConfig,
    EnvConfig,
    ReportingConfig,
    RiskConfig,
    StrategyConfig,
    VenueConfig,
)
from alpha_engine.contracts.mode import Mode
from alpha_engine.data.sources.synthetic_fixture import build_engine_with_synthetic_bars
from alpha_engine.engine.backtest import run_backtest
import alpha_engine.strategies.toy_buy_and_hold  # noqa: F401  (triggers @strategy registration)


def _data_loader(cfg, paths):
    engine, ids = build_engine_with_synthetic_bars(n_bars=10)
    return engine, ids


def _make_cfg(env_name: str) -> EnvConfig:
    return EnvConfig(
        env_name=env_name,
        mode=Mode.BACKTEST,
        strategy=StrategyConfig(ref="toy_buy_and_hold", params={"qty": 10, "buy_on_bar": 3}),
        venue=VenueConfig(id="nasdaq_sim", account_kind="paper"),
        data=DataConfig(
            live_source="venue",
            historical_source="synthetic_fixture",
            instruments=("MSFT.NASDAQ",),
        ),
        risk=RiskConfig(),
        reporting=ReportingConfig(timezone="UTC"),
    )


def test_backtest_runs_and_produces_trades_and_summary(tmp_path: Path):
    paths = EnvPaths(envs_root=tmp_path, env_name="toy")
    cfg = _make_cfg("toy")
    result = run_backtest(cfg=cfg, paths=paths, data_loader=_data_loader)

    assert result.halt_cause is None
    assert result.trades_path.exists()
    assert result.summary_path.exists()

    trades = pd.read_parquet(result.trades_path)
    # Toy strategy buys on bar 3 (configured) and sells on stop → at least 2 fills.
    assert len(trades) >= 2
    # Side column must be human-readable strings, not Nautilus enum reprs.
    # If this regresses, downstream PnL/win_rate go silently to zero.
    assert set(trades["side"].unique()) <= {"BUY", "SELL"}, trades["side"].unique()

    summary = json.loads(result.summary_path.read_text())
    assert summary["run_id"] == result.run_id
    assert summary["env_name"] == "toy"
    assert summary["mode"] == "backtest"
    assert summary["metrics"]["trades"] >= 2
    # Synthetic fixture rises monotonically; toy buy-then-sell must be profitable.
    assert summary["metrics"]["total_pnl"] > 0, summary["metrics"]
    assert summary["metrics"]["win_rate"] == 1.0, summary["metrics"]

    # JSONL logs were written.
    assert (paths.logs_dir / "engine.jsonl").exists()
    assert (paths.logs_dir / "orders.jsonl").exists()
