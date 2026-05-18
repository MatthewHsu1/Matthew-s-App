"""Msgbus payload published by `BBandScanActor` when Day-1 triggers fire."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SETUP_DETECTED_TOPIC: str = "setup.detected"


@dataclass(frozen=True)
class SetupDetected:
    """Day-1 setup detection event. Producer: BBandScanActor. Consumer: BBandTradingStrategy."""

    symbol: str
    ts: datetime
    day1_close: float
    day1_low: float
