"""Unit tests for the SetupDetected payload + topic constant."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC, SetupDetected


def test_topic_constant_is_stable() -> None:
    assert SETUP_DETECTED_TOPIC == "setup.detected"


def test_payload_fields_round_trip() -> None:
    ts = datetime(2026, 1, 21, tzinfo=timezone.utc)
    payload = SetupDetected(
        symbol="AAPL.NASDAQ", ts=ts, day1_close=97.5, day1_low=96.0
    )
    assert payload.symbol == "AAPL.NASDAQ"
    assert payload.ts == ts
    assert payload.day1_close == 97.5
    assert payload.day1_low == 96.0


def test_payload_is_frozen() -> None:
    payload = SetupDetected(
        symbol="AAPL.NASDAQ",
        ts=datetime(2026, 1, 21, tzinfo=timezone.utc),
        day1_close=97.5,
        day1_low=96.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError is a subclass of Exception
        payload.symbol = "MSFT.NASDAQ"  # type: ignore[misc]
