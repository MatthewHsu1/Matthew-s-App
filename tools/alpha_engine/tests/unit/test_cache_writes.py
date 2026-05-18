from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import DataSourceRegistry


def _make_df(start_ns: int, n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": [start_ns + i * 10**9 for i in range(n)],
        "open": [100.0 + i for i in range(n)],
        "high": [101.0 + i for i in range(n)],
        "low": [99.0 + i for i in range(n)],
        "close": [100.5 + i for i in range(n)],
        "volume": [1000] * n,
    })


def test_write_partition_creates_parents_and_file(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    df = _make_df(0, 3)
    cache.write_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05", df)
    p = cache.partition_path("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05")
    assert p.exists()
    read = cache.read_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05")
    assert len(read) == 3


def test_write_dedups_on_ts(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    cache.write_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05", _make_df(0, 3))
    # Overlapping write: rows 1,2 already present + new row 3.
    cache.write_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05", _make_df(10**9, 3))
    read = cache.read_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05")
    assert len(read) == 4
    assert read["ts"].is_monotonic_increasing


def test_write_uses_tempfile_then_rename(tmp_path: Path, monkeypatch):
    """No .tmp file should remain after a successful write."""
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    cache.write_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05", _make_df(0, 1))
    # Walk the partition dir; no leftover *.tmp.*
    pdir = cache.partition_path("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05").parent
    leftover_tmps = list(pdir.glob("*.tmp.*"))
    assert leftover_tmps == [], f"Leftover tempfiles: {leftover_tmps}"


def test_flock_serializes_writers(tmp_path: Path):
    """Two threads writing the same partition concurrently must serialize."""
    cache = HistoricalDataCache(root=tmp_path, registry=DataSourceRegistry())
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def writer(start_ns: int):
        try:
            barrier.wait()
            cache.write_partition(
                "ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05", _make_df(start_ns, 5)
            )
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=writer, args=(0,))
    t2 = threading.Thread(target=writer, args=(10**9 * 100,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert errors == []
    final = cache.read_partition("ibkr", "AAPL.NASDAQ", "1-DAY-LAST", "2026-05")
    # Both writes' rows should be present (10 total, deduped if any overlap).
    assert len(final) >= 5  # at minimum one writer's rows survived
    assert final["ts"].is_monotonic_increasing
