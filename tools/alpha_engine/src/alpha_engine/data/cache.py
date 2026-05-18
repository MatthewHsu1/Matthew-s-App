"""Shared historical Parquet cache.

Layout (spec §6.3):
  <root>/historical/<venue>/<instrument_id>/<bar_spec>/<period>.parquet
  <root>/.locks/<venue>__<instrument_id>__<bar_spec>__<period>.lock
"""
from __future__ import annotations

import fcntl
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from datetime import datetime

    from alpha_engine.data.registry import DataSourceRegistry


SCHEMA_COLUMNS = ("ts", "open", "high", "low", "close", "volume")


def _empty_bars_df() -> pd.DataFrame:
    return pd.DataFrame({
        "ts": pd.Series([], dtype="int64"),
        "open": pd.Series([], dtype="float64"),
        "high": pd.Series([], dtype="float64"),
        "low": pd.Series([], dtype="float64"),
        "close": pd.Series([], dtype="float64"),
        "volume": pd.Series([], dtype="int64"),
    })


class CacheLockTimeoutError(TimeoutError):
    """Raised when the per-key flock cannot be acquired within the timeout."""


@contextmanager
def _flock(path: Path, timeout_s: float = 30.0):
    """Block-acquire an exclusive flock on `path`. Raises after `timeout_s`."""

    path.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)

    try:
        deadline = time.monotonic() + timeout_s

        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise CacheLockTimeoutError(f"could not acquire lock {path}") from None
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


class HistoricalDataCache:
    def __init__(self, root: Path, registry: DataSourceRegistry) -> None:
        self._root = Path(root)
        self._registry = registry

    def partition_path(
        self, venue: str, instrument_id: str, bar_spec: str, period_key: str
    ) -> Path:
        return (
            self._root
            / "historical"
            / venue
            / instrument_id
            / bar_spec
            / f"{period_key}.parquet"
        )

    def lock_path(
        self, venue: str, instrument_id: str, bar_spec: str, period_key: str
    ) -> Path:
        name = f"{venue}__{instrument_id}__{bar_spec}__{period_key}.lock"
        return self._root / ".locks" / name

    def read_partition(
        self, venue: str, instrument_id: str, bar_spec: str, period_key: str
    ) -> pd.DataFrame:
        path = self.partition_path(venue, instrument_id, bar_spec, period_key)

        if not path.exists():
            return _empty_bars_df()
        
        try:
            table = pq.read_table(path)

            return table.to_pandas()
        except pa.ArrowInvalid:
            # Corrupted partition; delete and treat as missing. Caller re-fetches.
            path.unlink(missing_ok=True)

            return _empty_bars_df()

    def write_partition(
        self,
        venue: str,
        instrument_id: str,
        bar_spec: str,
        period_key: str,
        df: pd.DataFrame,
    ) -> None:
        path = self.partition_path(venue, instrument_id, bar_spec, period_key)
        lock = self.lock_path(venue, instrument_id, bar_spec, period_key)

        with _flock(lock):
            existing = self.read_partition(venue, instrument_id, bar_spec, period_key)

            merged = (
                pd.concat([existing, df], ignore_index=True)
                .drop_duplicates(subset=["ts"], keep="last")
                .sort_values("ts")
                .reset_index(drop=True)
            )

            path.parent.mkdir(parents=True, exist_ok=True)

            tmp_fd, tmp_name = tempfile.mkstemp(
                prefix=f"{period_key}.tmp.",
                suffix=".parquet",
                dir=str(path.parent),
            )

            os.close(tmp_fd)

            tmp_path = Path(tmp_name)

            try:
                table = pa.Table.from_pandas(merged, preserve_index=False)

                pq.write_table(table, tmp_path)
                os.replace(tmp_path, path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)

    def fetch(
        self,
        *,
        venue: str,
        instrument_id: str,
        bar_spec: str,
        start: datetime,
        end: datetime,
        source_id: str,
    ) -> pd.DataFrame:
        from alpha_engine.data.partitioning import partitions_between, period_for

        periods = partitions_between(bar_spec, start, end)

        # Read what we already have.
        existing_frames = [
            self.read_partition(venue, instrument_id, bar_spec, p) for p in periods
        ]

        existing = (
            pd.concat(existing_frames, ignore_index=True)
            if existing_frames
            else _empty_bars_df()
        )

        start_ns = int(pd.Timestamp(start).value)
        end_ns = int(pd.Timestamp(end).value)

        # Compute gap. Phase 2 keeps this simple: if any expected bar timestamp
        # is missing from `existing`, refetch the entire requested range from
        # the source. Smarter range diffing can come in Phase 2.1.
        missing = existing.empty or (
            existing["ts"].min() > start_ns or existing["ts"].max() < end_ns
        )

        if missing:
            source = self._resolve_source(source_id)
            fetched = source.fetch(instrument_id, bar_spec, start, end)

            # Write fetched rows back, partition by partition.
            if not fetched.empty:
                fetched_ts = pd.to_datetime(fetched["ts"], utc=True)

                for period_key in sorted({
                    period_for(bar_spec, t.to_pydatetime()) for t in fetched_ts
                }):
                    mask = fetched_ts.apply(
                        lambda t, pk=period_key: period_for(bar_spec, t.to_pydatetime()) == pk
                    )

                    chunk = fetched.loc[mask].reset_index(drop=True)

                    if not chunk.empty:
                        self.write_partition(venue, instrument_id, bar_spec, period_key, chunk)

            # Re-read merged state.
            existing_frames = [
                self.read_partition(venue, instrument_id, bar_spec, p) for p in periods
            ]

            existing = (
                pd.concat(existing_frames, ignore_index=True)
                if existing_frames
                else _empty_bars_df()
            )

        # Filter to requested range.
        in_range = existing[(existing["ts"] >= start_ns) & (existing["ts"] <= end_ns)]

        return in_range.sort_values("ts").reset_index(drop=True)

    def _resolve_source(self, source_id: str):
        # Test-injection hook (see test_cache_fetch.py).
        injected = getattr(self, "_inject_source_for_test", None)

        if injected is not None:
            return injected
        
        cls = self._registry.get(source_id)
        return cls()
