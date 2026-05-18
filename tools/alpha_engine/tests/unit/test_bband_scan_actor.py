"""Unit tests for BBandScanActor wiring.

Tactic: construct the actor, then replace its collaborators with fakes so we
can drive on_bar() directly and assert on what got published. Avoids spinning
up a BacktestEngine.

Nautilus's Actor base class is Cython-compiled and its `msgbus` attribute is
read-only, so direct injection of a fake msgbus is not possible. Instead, we
spy on the `_publish_setup` method, which is a pure-Python override seam
defined on BBandScanActor for exactly this purpose. `subscribe_bars` and
`request_bars` are also Cython methods, but Python subclass instance
dictionaries shadow them cleanly via normal attribute assignment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Price, Quantity

from alpha_engine.scan.bband_scan_actor import (
    BBandScanActor,
    BBandScanActorConfig,
)
from alpha_engine.scan.setup_detected import SetupDetected


def _daily_bar_type(iid: InstrumentId) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def _make_bar(iid: InstrumentId, ts: datetime, *, close: float, low: float, volume: float) -> Bar:
    ts_ns = int(ts.timestamp() * 1e9)
    return Bar(
        bar_type=_daily_bar_type(iid),
        open=Price.from_str(f"{close:.2f}"),
        high=Price.from_str(f"{close:.2f}"),
        low=Price.from_str(f"{low:.2f}"),
        close=Price.from_str(f"{close:.2f}"),
        volume=Quantity.from_int(int(volume)),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


@pytest.fixture
def actor() -> BBandScanActor:
    cfg = BBandScanActorConfig(
        instrument_ids=["AAPL.NASDAQ", "MSFT.NASDAQ"],
        bband_period=20,
        bband_stddev=2.0,
        volume_avg_period=20,
        day1_volume_multiplier=2.0,
    )
    inst = BBandScanActor(cfg)
    # Inject fakes for the Nautilus collaborators we exercise.
    # subscribe_bars / request_bars: Python subclass instance dict shadows them.
    inst._fake_subscribe = MagicMock()
    inst.subscribe_bars = inst._fake_subscribe  # type: ignore[assignment]
    inst._fake_request = MagicMock()
    inst.request_bars = inst._fake_request  # type: ignore[assignment]
    # _publish_setup: overridable Python seam (msgbus is Cython read-only).
    inst._fake_publish = MagicMock()
    inst._publish_setup = inst._fake_publish  # type: ignore[assignment]
    return inst


def test_on_start_subscribes_daily_bars_per_instrument(actor: BBandScanActor) -> None:
    actor.on_start()
    assert actor._fake_subscribe.call_count == 2
    subscribed = [call.args[0] for call in actor._fake_subscribe.call_args_list]
    aggregations = {bt.spec.aggregation for bt in subscribed}
    assert aggregations == {BarAggregation.DAY}


def test_on_start_requests_warmup_bars(actor: BBandScanActor) -> None:
    actor.on_start()
    # 20 prior bars per symbol (BBandVolumeSetupParams.bband_period).
    assert actor._fake_request.call_count == 2
    for call in actor._fake_request.call_args_list:
        assert call.kwargs.get("limit") == 20 or 20 in call.args


def test_on_bar_publishes_payload_when_trigger_fires(actor: BBandScanActor) -> None:
    iid = InstrumentId.from_str("AAPL.NASDAQ")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # 20 alternating-price warmup bars.
    for i in range(20):
        px = 100.0 + (1.5 if i % 2 == 0 else -1.5)
        actor.on_bar(_make_bar(iid, start + timedelta(days=i), close=px, low=px - 0.5, volume=1_000_000))

    actor._fake_publish.reset_mock()

    trigger = _make_bar(
        iid,
        start + timedelta(days=20),
        close=97.5,
        low=96.0,
        volume=2_500_000,
    )
    actor.on_bar(trigger)

    actor._fake_publish.assert_called_once()
    call = actor._fake_publish.call_args
    payload = call.args[0]
    assert isinstance(payload, SetupDetected)
    assert payload.symbol == "AAPL.NASDAQ"
    assert payload.day1_close == 97.5
    assert payload.day1_low == 96.0


def test_on_bar_does_not_publish_when_conditions_unmet(actor: BBandScanActor) -> None:
    iid = InstrumentId.from_str("AAPL.NASDAQ")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(20):
        actor.on_bar(_make_bar(iid, start + timedelta(days=i), close=100.0, low=100.0, volume=1_000_000))
    actor._fake_publish.reset_mock()

    quiet = _make_bar(iid, start + timedelta(days=20), close=100.0, low=99.5, volume=1_000_000)
    actor.on_bar(quiet)

    actor._fake_publish.assert_not_called()


def test_on_bar_ignores_non_daily_aggregation(actor: BBandScanActor) -> None:
    """A 5-minute bar accidentally routed here must be ignored, not crash."""
    iid = InstrumentId.from_str("AAPL.NASDAQ")
    ts = datetime(2026, 1, 21, 14, 30, tzinfo=timezone.utc)
    ts_ns = int(ts.timestamp() * 1e9)
    five_min_bar = Bar(
        bar_type=BarType(
            instrument_id=iid,
            bar_spec=BarSpecification(5, BarAggregation.MINUTE, PriceType.LAST),
            aggregation_source=AggregationSource.EXTERNAL,
        ),
        open=Price.from_str("100.00"),
        high=Price.from_str("100.00"),
        low=Price.from_str("100.00"),
        close=Price.from_str("100.00"),
        volume=Quantity.from_int(1000),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )
    actor._fake_publish.reset_mock()
    actor.on_bar(five_min_bar)
    actor._fake_publish.assert_not_called()
