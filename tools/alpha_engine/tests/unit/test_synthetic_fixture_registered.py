from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

# Importing the sources package triggers @data_source registration.
import alpha_engine.data.sources  # noqa: F401  # pyright: ignore[reportUnusedImport]
from alpha_engine.data.registry import default_registry


def test_synthetic_fixture_is_registered():
    assert "synthetic_fixture" in default_registry.list()


def test_synthetic_source_returns_dataframe_with_required_schema():
    src_cls = default_registry.get("synthetic_fixture")
    src = src_cls()
    df = src.fetch(
        instrument_id="AAPL.NASDAQ",
        bar_spec="1-DAY-LAST",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 10, tzinfo=timezone.utc),
    )
    assert isinstance(df, pd.DataFrame)
    required_columns = {"ts", "open", "high", "low", "close", "volume"}
    assert required_columns.issubset(df.columns), (
        f"missing columns: {required_columns - set(df.columns)}"
    )
    assert len(df) > 0
    # ts must be int64 ns since epoch per spec §6.2.
    assert df["ts"].dtype.kind == "i", f"ts dtype {df['ts'].dtype} is not int"
