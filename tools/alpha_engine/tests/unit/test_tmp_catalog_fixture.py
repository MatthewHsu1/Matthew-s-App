"""Tests the tmp_catalog test helper itself."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from nautilus_trader.model.data import Bar
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from tests.fixtures.tmp_catalog import build_tmp_catalog


def test_build_tmp_catalog_writes_readable_bars(tmp_path: Path) -> None:
    catalog = build_tmp_catalog(
        root=tmp_path,
        symbol="MSFT",
        venue="NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2024, 1, 2, tzinfo=timezone.utc),
        n_bars=5,
    )

    assert isinstance(catalog, ParquetDataCatalog)

    bars = catalog.bars(
        bar_types=["MSFT.NASDAQ-1-DAY-LAST-EXTERNAL"],
    )

    assert len(bars) == 5
    assert all(isinstance(b, Bar) for b in bars)
    assert bars[0].ts_event < bars[-1].ts_event
