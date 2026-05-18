from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import alpha_engine.data.sources  # noqa: F401  (registers synthetic_fixture)
from alpha_engine.data.cache import HistoricalDataCache
from alpha_engine.data.registry import default_registry


def test_two_writers_same_partition_no_torn_files(tmp_path: Path):
    cache = HistoricalDataCache(root=tmp_path, registry=default_registry)
    barrier = threading.Barrier(2)

    def run(seed_offset_days: int):
        barrier.wait()
        cache.fetch(
            venue="test",
            instrument_id=f"INSTR{seed_offset_days}.NASDAQ",
            bar_spec="1-DAY-LAST",
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 5, tzinfo=timezone.utc),
            source_id="synthetic_fixture",
        )

    threads = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No leftover tempfiles anywhere under historical/.
    leftovers = list((tmp_path / "historical").rglob("*.tmp.*"))
    assert leftovers == []
