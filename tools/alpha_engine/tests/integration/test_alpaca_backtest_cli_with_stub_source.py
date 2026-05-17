"""End-to-end CLI test: `env start` dispatches alpaca_historical through the
cache loader and writes reports just like the synthetic path does.

A stub source replaces the real Alpaca source by registering itself under the
ID `alpaca_historical` for the duration of the test. The cache root is
redirected to tmp_path so we don't pollute the real shared cache.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alpha_engine.cli_commands import env_start
import alpha_engine.data.sources  # noqa: F401  (ensure registrations happen first)
from alpha_engine.data.registry import default_registry


class _StubAlpacaSource:
    """Deterministic in-memory bars; covers DAILY and MINUTE specs."""

    def fetch(self, instrument_id, bar_spec, start, end):
        spec_upper = bar_spec.upper()
        if "DAY" in spec_upper:
            ts_index = pd.date_range(start=start, end=end, freq="1D", tz="UTC")
        else:
            ts_index = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
        n = len(ts_index)
        if n == 0:
            return pd.DataFrame({
                "ts": pd.Series([], dtype="int64"),
                "open": pd.Series([], dtype="float64"),
                "high": pd.Series([], dtype="float64"),
                "low": pd.Series([], dtype="float64"),
                "close": pd.Series([], dtype="float64"),
                "volume": pd.Series([], dtype="int64"),
            })
        base = 100.0 + np.arange(n, dtype="float64") * 0.05
        return pd.DataFrame({
            "ts": ts_index.view("int64"),
            "open": base,
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base + 0.1,
            "volume": np.full(n, 1000, dtype="int64"),
        })


@pytest.fixture
def stub_alpaca_source():
    """Swap the registered alpaca_historical class for the test duration."""
    saved = default_registry._classes.get("alpaca_historical")
    if "alpaca_historical" in default_registry._classes:
        del default_registry._classes["alpaca_historical"]
    default_registry.register("alpaca_historical", _StubAlpacaSource)
    yield
    if "alpaca_historical" in default_registry._classes:
        del default_registry._classes["alpaca_historical"]
    if saved is not None:
        default_registry.register("alpaca_historical", saved)


def test_env_start_with_alpaca_historical_writes_reports(
    tmp_path: Path, stub_alpaca_source, monkeypatch,
) -> None:
    # Point cache root at tmp_path so partition writes don't escape the test.
    from alpha_engine.engine import cache_loader
    monkeypatch.setattr(cache_loader, "_cache_root", lambda: tmp_path / "cache")

    envs_root = tmp_path / "envs"
    env_dir = envs_root / "alpaca_bt"
    env_dir.mkdir(parents=True)
    config = {
        "env_name": "alpaca_bt",
        "mode": "backtest",
        "strategy": {
            "ref": "bband_volume_setup",
            "params": {"tranche_size_qty": 10, "minute_bar_step": 1},
        },
        "venue": {"id": "nasdaq_sim", "account_kind": "paper"},
        "data": {
            "live_source": "venue",
            "historical_source": "alpaca_historical",
            "instruments": ["MSFT.NASDAQ"],
            "bar_spec": "1-DAY-LAST",
            "start_date": "2025-01-02",
            "end_date": "2025-01-05",
        },
        "risk": {},
        "reporting": {"timezone": "UTC"},
    }
    (env_dir / "config.json").write_text(json.dumps(config))

    rc = env_start.run(envs_root=envs_root, name="alpaca_bt")
    assert rc == 0, f"env_start returned non-zero rc={rc}"

    reports_dir = env_dir / "reports"
    assert (reports_dir / "trades.parquet").exists()
    summaries = list(reports_dir.glob("summary_*.json"))
    assert len(summaries) == 1, f"expected exactly one summary file, got {summaries}"

    summary = json.loads(summaries[0].read_text())
    assert summary["env_name"] == "alpaca_bt"
    assert summary["mode"] == "backtest"
