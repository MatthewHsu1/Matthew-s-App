"""Pre-flight: verify the alpaca-py classes our historical source uses still exist
with the field names we depend on.

If this fails, pin a known-good version or adjust sources/alpaca_historical.py.
"""
from __future__ import annotations


def test_imports():
    from alpaca.data.historical import StockHistoricalDataClient  # noqa: F401
    from alpaca.data.requests import StockBarsRequest  # noqa: F401
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit  # noqa: F401


def test_bars_request_has_required_fields():
    from alpaca.data.requests import StockBarsRequest
    # alpaca-py uses pydantic; model_fields enumerates the schema.
    assert hasattr(StockBarsRequest, "model_fields"), "alpaca-py changed away from pydantic"
    fields = set(StockBarsRequest.model_fields.keys())
    required = {"symbol_or_symbols", "timeframe", "start", "end"}
    missing = required - fields
    assert not missing, f"StockBarsRequest is missing fields {missing}; available: {sorted(fields)}"


def test_timeframe_has_day_and_minute():
    from alpaca.data.timeframe import TimeFrame
    assert hasattr(TimeFrame, "Day"), "TimeFrame.Day missing"
    assert hasattr(TimeFrame, "Minute"), "TimeFrame.Minute missing"


def test_client_constructs_without_credentials_for_offline_use():
    """Client init should not network during construction."""
    from alpaca.data.historical import StockHistoricalDataClient
    # Construct with dummy keys; real credentials only matter when calling endpoints.
    client = StockHistoricalDataClient(api_key="dummy", secret_key="dummy")
    assert client is not None
