"""Tests for the thinned reporting.summary writer."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from alpha_engine.reporting.summary import RunMetadata, write_summary


def test_write_summary_emits_metadata_and_metrics(tmp_path: Path):
    meta = RunMetadata(
        trader_id="BBAND-V1-BACKTEST",
        instance_id="00000000-0000-0000-0000-000000000001",
        git_sha="abc123",
        env_name="bband_v1",
        start_ts=datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc),
        end_ts=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
    )
    stats_pnls = {"USD": {"PnL (total)": 1234.5, "Sharpe Ratio": 1.2}}
    stats_returns = {"Annual Volatility (%)": 12.3}

    out = tmp_path / "summary.json"
    write_summary(out, meta=meta, stats_pnls=stats_pnls, stats_returns=stats_returns)

    data = json.loads(out.read_text())
    assert data["trader_id"] == "BBAND-V1-BACKTEST"
    assert data["instance_id"] == "00000000-0000-0000-0000-000000000001"
    assert data["git_sha"] == "abc123"
    assert data["env_name"] == "bband_v1"
    assert data["start_ts"] == "2026-01-02T14:00:00+00:00"
    assert data["end_ts"] == "2026-01-02T16:00:00+00:00"
    assert data["metrics"]["pnls"]["USD"]["PnL (total)"] == 1234.5
    assert data["metrics"]["returns"]["Annual Volatility (%)"] == 12.3


def test_write_summary_creates_parent_dirs(tmp_path: Path):
    out = tmp_path / "nested" / "subdir" / "summary.json"
    meta = RunMetadata(
        trader_id="X",
        instance_id="i",
        git_sha=None,
        env_name="e",
        start_ts=datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc),
        end_ts=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
    )
    write_summary(out, meta=meta, stats_pnls={}, stats_returns={})
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["git_sha"] is None
    assert data["metrics"] == {"pnls": {}, "returns": {}}
