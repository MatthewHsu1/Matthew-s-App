from __future__ import annotations

from datetime import datetime, timezone

import pytest

from alpha_engine.data.partitioning import period_for, partitions_between


def _ts(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


def test_daily_spec_uses_monthly_partition():
    assert period_for("1-DAY-LAST", _ts(2026, 5, 15)) == "2026-05"


def test_minute_spec_uses_daily_partition():
    assert period_for("1-MIN-LAST", _ts(2026, 5, 15, 14)) == "2026-05-15"


def test_hour_spec_uses_monthly_partition():
    assert period_for("1-HOUR-LAST", _ts(2026, 5, 15)) == "2026-05"


def test_second_spec_uses_daily_partition():
    assert period_for("5-SECOND-LAST", _ts(2026, 5, 15)) == "2026-05-15"


def test_unsupported_unit_raises():
    with pytest.raises(ValueError, match="unsupported"):
        period_for("1-WEEK-LAST", _ts(2026, 5, 15))


def test_partitions_between_daily_spec_spans_months():
    parts = partitions_between(
        "1-DAY-LAST",
        _ts(2026, 1, 15),
        _ts(2026, 3, 5),
    )
    assert parts == ["2026-01", "2026-02", "2026-03"]


def test_partitions_between_minute_spec_spans_days():
    parts = partitions_between(
        "1-MIN-LAST",
        _ts(2026, 5, 1, 23),
        _ts(2026, 5, 3, 1),
    )
    assert parts == ["2026-05-01", "2026-05-02", "2026-05-03"]
