from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import alpha_engine.data.sources  # noqa: F401
from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import default_registry


def test_synthetic_fetch_populates_cache(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=default_registry)
    df = cache.fetch(
        venue="test",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        source_id="synthetic_fixture",
    )
    assert len(df) > 0

    # Partition files exist on disk (Jan + Feb).
    jan_path = cache.partition_path("test", "AAPL.NASDAQ", "1-DAY-LAST", "2026-01")
    feb_path = cache.partition_path("test", "AAPL.NASDAQ", "1-DAY-LAST", "2026-02")
    assert jan_path.exists()
    assert feb_path.exists()


def test_second_fetch_uses_cache(tmp_path: Path, monkeypatch):
    cache = HistoricalDataCache(root=tmp_path, registry=default_registry)

    # First fetch populates.
    args = dict(
        venue="test",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        source_id="synthetic_fixture",
    )
    cache.fetch(**args)

    # Replace the source with one that fails if called.
    class _Boom:
        def fetch(self, *a, **k):
            raise AssertionError("source should NOT be called on second fetch")

    cache._inject_source_for_test = _Boom()  # type: ignore[attr-defined]
    df2 = cache.fetch(**args)
    assert len(df2) > 0


def test_minute_spec_partitions_by_day(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=default_registry)
    cache.fetch(
        venue="test",
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-MIN-LAST",
        start=datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 16, 0, tzinfo=timezone.utc),
        source_id="synthetic_fixture",
    )
    p1 = cache.partition_path("test", "AAPL.NASDAQ", "1-MIN-LAST", "2026-01-01")
    p2 = cache.partition_path("test", "AAPL.NASDAQ", "1-MIN-LAST", "2026-01-02")
    assert p1.exists()
    assert p2.exists()
