from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import DataSourceRegistry


def test_partition_path(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    p = cache.partition_path(
        venue="ibkr",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        period_key="2026-05",
    )
    assert p == tmp_path / "historical" / "ibkr" / "AAPL.NASDAQ" / "1-DAY-LAST" / "2026-05.parquet"


def test_lock_path(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    lp = cache.lock_path(
        venue="ibkr",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        period_key="2026-05",
    )
    assert lp == tmp_path / ".locks" / "ibkr__AAPL.NASDAQ__1-DAY-LAST__2026-05.lock"


def test_read_partition_returns_empty_when_absent(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    df = cache.read_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05")
    assert df.empty
    assert list(df.columns) == ["ts", "open", "high", "low", "close", "volume"]
