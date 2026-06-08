"""FloorScanActor thin Nautilus shell tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Price, Quantity

from alpha_engine.scan.setup_detected import SetupDetected
from alpha_engine.strategies.floor_trading.scan_actor import FloorScanActor, FloorScanActorConfig

_IID = "AAPL.NASDAQ"
_T0 = datetime(2026, 1, 5, 21, 0, tzinfo=timezone.utc)


def _make_actor() -> FloorScanActor:
    cfg = FloorScanActorConfig(
        instrument_ids=[_IID],
        bband_period=20,
        bband_stddev=2.0,
        volume_avg_period=20,
        day1_volume_multiplier=2.0,
    )
    actor = FloorScanActor(config=cfg)
    # Shadow Cython-sealed methods via instance __dict__.
    actor.subscribe_bars = MagicMock()  # type: ignore[assignment]
    actor.request_bars = MagicMock()  # type: ignore[assignment]
    # clock is Cython read-only: override the Python seam instead.
    actor._warmup_start_dt = lambda: _T0  # type: ignore[assignment]
    # msgbus is Cython read-only: spy on the _publish_setup seam.
    actor._fake_publish = MagicMock()
    actor._publish_setup = actor._fake_publish  # type: ignore[assignment]
    return actor


def _daily_bar_type(iid: InstrumentId) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def _make_bar(iid: InstrumentId, ts: datetime, *, close: float, low: float, volume: float) -> Bar:
    ts_ns = int(ts.timestamp() * 1e9)
    high = max(close, low) + 0.01
    open_ = close
    return Bar(
        bar_type=_daily_bar_type(iid),
        open=Price.from_str(f"{open_:.2f}"),
        high=Price.from_str(f"{high:.2f}"),
        low=Price.from_str(f"{low:.2f}"),
        close=Price.from_str(f"{close:.2f}"),
        volume=Quantity.from_int(int(volume)),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )


def test_actor_publishes_setup_when_logic_fires() -> None:
    actor = _make_actor()
    iid = InstrumentId.from_str(_IID)
    # Feed 20 prior bars + 1 trigger bar.
    for i in range(20):
        actor.on_bar(_make_bar(iid, _T0 + timedelta(days=i), low=99.9, close=100.0, volume=1_000))
    actor.on_bar(_make_bar(iid, _T0 + timedelta(days=20), low=99.0, close=99.5, volume=3_000))

    actor._fake_publish.assert_called_once()
    payload = actor._fake_publish.call_args.args[0]
    assert isinstance(payload, SetupDetected)
    assert payload.symbol == _IID
    assert payload.day1_close == 99.5


def test_actor_ignores_non_day_aggregation() -> None:
    actor = _make_actor()
    iid = InstrumentId.from_str(_IID)
    ts_ns = int(_T0.timestamp() * 1e9)
    minute_bar = Bar(
        bar_type=BarType(
            instrument_id=iid,
            bar_spec=BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST),
            aggregation_source=AggregationSource.EXTERNAL,
        ),
        open=Price.from_str("99.90"),
        high=Price.from_str("100.00"),
        low=Price.from_str("99.50"),
        close=Price.from_str("99.90"),
        volume=Quantity.from_int(3000),
        ts_event=ts_ns,
        ts_init=ts_ns,
    )
    actor.on_bar(minute_bar)
    actor._fake_publish.assert_not_called()


def test_on_start_subscribes_and_requests_warmup_per_instrument() -> None:
    actor = _make_actor()
    actor.on_start()
    # Single instrument in the config (_IID), so each should be called once.
    assert actor.subscribe_bars.call_count == 1
    assert actor.request_bars.call_count == 1
    # The subscribed bar_type should be the 1-DAY-LAST EXTERNAL bar.
    sub_bar_type = actor.subscribe_bars.call_args.args[0]
    assert str(sub_bar_type).endswith("1-DAY-LAST-EXTERNAL")
