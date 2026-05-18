"""Nautilus Actor that screens the universe for Day-1 setups.

Subscribes to 1-day bars for every configured instrument, evaluates
`is_day1_setup` per bar via `BBandScanLogic`, and publishes a `SetupDetected`
event on msgbus topic `"setup.detected"` for every positive hit. The
strategy (`BBandTradingStrategy`) consumes those events and seeds its state
machine on receipt.

All business logic lives in `BBandScanLogic` (Nautilus-free, fully unit-tested
against `is_day1_setup`). This module is a thin shell.
"""
from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId

from alpha_engine.scan.bband_scan_logic import BBandScanLogic, ScanBar
from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC
from alpha_engine.strategies.bband_volume_setup.params import (
    BBandVolumeSetupParams,
)


class BBandScanActorConfig(ActorConfig):
    instrument_ids: list[str]
    bband_period: int = 20
    bband_stddev: float = 2.0
    volume_avg_period: int = 20
    day1_volume_multiplier: float = 2.0


def _daily_bar_type(iid: InstrumentId) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


class BBandScanActor(Actor):
    def __init__(self, config: BBandScanActorConfig) -> None:
        super().__init__(config=config)
        self._cfg = config
        # Strategy and scan share these tunables; spike/surge are strategy-only
        # so we pass placeholder zeros — they are not read by `is_day1_setup`.
        params = BBandVolumeSetupParams(
            bband_period=config.bband_period,
            bband_stddev=config.bband_stddev,
            volume_avg_period=config.volume_avg_period,
            day1_volume_multiplier=config.day1_volume_multiplier,
            spike_volume_multiplier=0.0,
            spike_price_move_pct=0.0,
            surge_volume_multiplier=0.0,
            surge_requires_price_below_open=False,
            surge_min_gap_minutes=0,
            tranche_count=0,
            hard_stop_pct_below_day1_low=0.0,
            max_hold_days=0,
        )
        self._logic = BBandScanLogic(params)
        self._instruments: list[InstrumentId] = [
            InstrumentId.from_str(iid) for iid in config.instrument_ids
        ]

    def on_start(self) -> None:
        for iid in self._instruments:
            bar_type = _daily_bar_type(iid)
            self.subscribe_bars(bar_type)
            # Warm up the rolling window with `bband_period` prior bars.
            self.request_bars(bar_type, limit=self._cfg.bband_period)

    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type.spec.aggregation != BarAggregation.DAY:
            return
        ts = datetime.fromtimestamp(bar.ts_event / 1e9, tz=timezone.utc)
        scan_bar = ScanBar(
            symbol=str(bar.bar_type.instrument_id),
            ts=ts,
            low=float(bar.low),
            close=float(bar.close),
            volume=float(bar.volume),
        )
        payload = self._logic.on_daily_bar(scan_bar)
        if payload is not None:
            self._publish_setup(payload)

    def _publish_setup(self, payload: object) -> None:
        """Publish a SetupDetected payload on the msgbus.

        Extracted as an overridable method so tests can inject a spy without
        requiring Nautilus's Cython-sealed `msgbus` attribute to be writable.
        """
        self.msgbus.publish(topic=SETUP_DETECTED_TOPIC, msg=payload)
