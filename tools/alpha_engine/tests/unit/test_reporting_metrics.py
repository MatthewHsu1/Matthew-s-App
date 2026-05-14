from __future__ import annotations

import math

import pandas as pd

from alpha_engine.reporting.metrics import (
    total_pnl,
    win_rate,
    sharpe,
    max_drawdown,
    avg_holding_seconds,
)


def _trades_df():
    return pd.DataFrame(
        [
            {"ts": pd.Timestamp("2026-01-02 14:30", tz="UTC"), "side": "BUY",  "quantity": 10, "price": 100.0, "instrument_id": "X"},
            {"ts": pd.Timestamp("2026-01-02 15:30", tz="UTC"), "side": "SELL", "quantity": 10, "price": 105.0, "instrument_id": "X"},
            {"ts": pd.Timestamp("2026-01-03 14:30", tz="UTC"), "side": "BUY",  "quantity": 5,  "price": 200.0, "instrument_id": "X"},
            {"ts": pd.Timestamp("2026-01-03 14:45", tz="UTC"), "side": "SELL", "quantity": 5,  "price": 195.0, "instrument_id": "X"},
        ]
    )


def _pnl_daily_df():
    return pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-01-02"), "net_pnl": 50.0},
            {"date": pd.Timestamp("2026-01-03"), "net_pnl": -25.0},
            {"date": pd.Timestamp("2026-01-06"), "net_pnl": 75.0},
        ]
    )


def test_total_pnl_sums_daily():
    assert total_pnl(_pnl_daily_df()) == 100.0


def test_max_drawdown_finds_worst_peak_to_trough():
    dd = max_drawdown(_pnl_daily_df())
    assert dd == -25.0


def test_win_rate_counts_round_trips():
    rate = win_rate(_trades_df())
    assert rate == 0.5


def test_sharpe_handles_constant_returns():
    constant = pd.DataFrame(
        [
            {"date": pd.Timestamp("2026-01-02"), "net_pnl": 10.0},
            {"date": pd.Timestamp("2026-01-03"), "net_pnl": 10.0},
            {"date": pd.Timestamp("2026-01-06"), "net_pnl": 10.0},
        ]
    )
    s = sharpe(constant)
    assert s == 0.0


def test_avg_holding_seconds():
    secs = avg_holding_seconds(_trades_df())
    assert math.isclose(secs, 2250.0, rel_tol=1e-6)
