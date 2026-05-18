from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from alpha_engine.reporting.summary import RunMetadata, write_summary


def test_write_summary_round_trip(tmp_path: Path):
    trades = pd.DataFrame(
        [
            {"ts": pd.Timestamp("2026-01-02 14:30", tz="UTC"), "side": "BUY",  "quantity": 10, "price": 100.0, "instrument_id": "X"},
            {"ts": pd.Timestamp("2026-01-02 15:30", tz="UTC"), "side": "SELL", "quantity": 10, "price": 105.0, "instrument_id": "X"},
        ]
    )
    pnl_daily = pd.DataFrame([{"date": pd.Timestamp("2026-01-02"), "net_pnl": 50.0}])
    meta = RunMetadata(
        run_id="run_test",
        env_name="toy",
        mode="backtest",
        strategy_class="ToyBuyAndHold",
        start_ts=datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc),
        end_ts=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
        git_sha="abc123",
        halt_cause=None,
    )

    out = tmp_path / "summary.json"
    write_summary(out, meta=meta, trades=trades, pnl_daily=pnl_daily)

    data = json.loads(out.read_text())
    assert data["run_id"] == "run_test"
    assert data["mode"] == "backtest"
    assert data["metrics"]["total_pnl"] == 50.0
    assert data["metrics"]["trades"] == 2
    assert data["halt_cause"] is None
