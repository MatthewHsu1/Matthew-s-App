from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from alpha_engine.reporting.trades import TradeRecord, write_trades_parquet


def _trade(qty: float, px: float, side: str = "BUY") -> TradeRecord:
    return TradeRecord(
        ts=datetime(2026, 5, 14, 14, 30, 0, tzinfo=timezone.utc),
        run_id="run_test",
        env_name="toy",
        strategy_class="ToyBuyAndHold",
        instrument_id="MSFT.NASDAQ",
        side=side,
        quantity=qty,
        price=px,
        fees=0.01,
    )


def test_writes_parquet_with_expected_columns(tmp_path: Path):
    path = tmp_path / "trades.parquet"
    write_trades_parquet(path, [_trade(10, 100.0), _trade(5, 101.0, side="SELL")])
    df = pd.read_parquet(path)
    assert list(df.columns) == [
        "ts",
        "run_id",
        "env_name",
        "strategy_class",
        "instrument_id",
        "side",
        "quantity",
        "price",
        "fees",
    ]
    assert len(df) == 2
    assert df.iloc[0]["instrument_id"] == "MSFT.NASDAQ"


def test_empty_list_writes_empty_parquet(tmp_path: Path):
    path = tmp_path / "trades.parquet"
    write_trades_parquet(path, [])
    df = pd.read_parquet(path)
    assert len(df) == 0
