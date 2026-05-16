"""Partition-key resolution for the historical Parquet cache.

Per spec §3 decision #2:
  - Daily-and-coarser bar specs → monthly partitions ("YYYY-MM").
  - Minute-and-finer bar specs → daily partitions ("YYYY-MM-DD").
"""
from __future__ import annotations

from datetime import datetime, timedelta

_COARSE_UNITS = ("DAY", "HOUR")          # → monthly
_FINE_UNITS = ("MIN", "MINUTE", "SECOND")  # → daily


def _granularity(bar_spec: str) -> str:
    """Return 'monthly' or 'daily' for a Nautilus bar spec like '1-DAY-LAST'."""
    parts = bar_spec.upper().split("-")
    if len(parts) < 2:
        raise ValueError(f"unsupported bar_spec {bar_spec!r}: expected NUM-UNIT-PRICE")
    unit = parts[1]
    if unit in _COARSE_UNITS:
        return "monthly"
    if unit in _FINE_UNITS:
        return "daily"
    raise ValueError(f"unsupported bar_spec unit {unit!r} in {bar_spec!r}")


def period_for(bar_spec: str, ts: datetime) -> str:
    """Compute the partition key for a single timestamp."""
    if _granularity(bar_spec) == "monthly":
        return ts.strftime("%Y-%m")
    return ts.strftime("%Y-%m-%d")


def partitions_between(bar_spec: str, start: datetime, end: datetime) -> list[str]:
    """All partition keys covering [start, end] inclusive."""
    if end < start:
        return []
    gran = _granularity(bar_spec)
    seen: list[str] = []
    if gran == "monthly":
        # Step month-by-month.
        cursor = start.replace(day=1)
        end_marker = end.replace(day=1)
        while cursor <= end_marker:
            key = cursor.strftime("%Y-%m")
            if key not in seen:
                seen.append(key)
            # Advance one month.
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
    else:
        cursor = start
        while cursor.date() <= end.date():
            key = cursor.strftime("%Y-%m-%d")
            if key not in seen:
                seen.append(key)
            cursor = cursor + timedelta(days=1)
    return seen
