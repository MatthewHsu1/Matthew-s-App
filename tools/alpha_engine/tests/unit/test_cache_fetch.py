from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import DataSourceRegistry, data_source


class _CallCountingSource:
    def __init__(self):
        self.calls: list[tuple] = []

    def fetch(self, instrument_id, bar_spec, start, end):
        self.calls.append((instrument_id, bar_spec, start, end))
        # 3 daily bars starting at `start`
        ts0 = int(pd.Timestamp(start).value)
        return pd.DataFrame({
            "ts": [ts0, ts0 + 86_400_000_000_000, ts0 + 2 * 86_400_000_000_000],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1000, 1000],
        })


def test_first_fetch_calls_source_then_caches(tmp_path: Path):
    reg = DataSourceRegistry()
    src = _CallCountingSource()
    reg.register("counting", type("CountingCls", (), {"__call__": lambda self: src, "instance": src}))
    # Simpler: bypass the registry for the test and inject directly.
    cache = HistoricalDataCache(root=tmp_path, registry=reg)
    cache._inject_source_for_test = src  # type: ignore[attr-defined]

    df = cache.fetch(
        venue="test",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 3, tzinfo=timezone.utc),
        source_id="counting",
    )
    assert len(df) == 3
    assert len(src.calls) == 1


def test_second_fetch_hits_cache(tmp_path: Path):
    reg = DataSourceRegistry()
    src = _CallCountingSource()
    cache = HistoricalDataCache(root=tmp_path, registry=reg)
    cache._inject_source_for_test = src  # type: ignore[attr-defined]

    args = dict(
        venue="test",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 3, tzinfo=timezone.utc),
        source_id="counting",
    )
    cache.fetch(**args)
    cache.fetch(**args)
    assert len(src.calls) == 1, "Second fetch should not re-call the source"
