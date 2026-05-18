"""Nautilus `Strategy` wrapper around the pure BBand+Volume state machine.

Subscribes to one daily and one 5-minute bar stream per configured instrument,
routes each `Bar` event into the state machine, and translates emitted
`Intent`s into market orders. Exit positions track quantity per symbol so
EXIT_ALL liquidates exactly what was bought across all tranches.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AggregationSource,
    BarAggregation,
    OrderSide,
    PriceType,
)
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from alpha_engine.strategies.bband_volume_setup.state_machine import (
    BBandVolumeSetupParams,
    BBandVolumeSetupStateMachine,
    DailyBar,
    Intent,
    IntentKind,
    MinuteBar,
)
from alpha_engine.strategies.registry import strategy


class BBandVolumeSetupNautilusParams(StrategyConfig):
    """Config exposed to env.json. Splits Nautilus-level wiring from
    state-machine tunables so the engine can hand it to Nautilus directly."""

    instrument_ids: list[str]
    tranche_size_qty: int = 10
    minute_bar_step: int = 5
    # State-machine tunables (all optional; defaults match Phase 2 v0 spec).
    bband_period: int = 20
    bband_stddev: float = 2.0
    volume_avg_period: int = 20
    day1_volume_multiplier: float = 2.0
    spike_volume_multiplier: float = 3.0
    spike_price_move_pct: float = 1.5
    surge_volume_multiplier: float = 2.0
    surge_requires_price_below_open: bool = True
    surge_min_gap_minutes: int = 30
    tranche_count: int = 3
    hard_stop_pct_below_day1_low: float = 2.0
    max_hold_days: int = 5


@strategy("bband_volume_setup")
class BBandVolumeSetupStrategy(Strategy):
    def __init__(self, config: BBandVolumeSetupNautilusParams) -> None:
        super().__init__(config=config)
        self._cfg = config
        self._state_machine = BBandVolumeSetupStateMachine(
            BBandVolumeSetupParams(
                bband_period=config.bband_period,
                bband_stddev=config.bband_stddev,
                volume_avg_period=config.volume_avg_period,
                day1_volume_multiplier=config.day1_volume_multiplier,
                spike_volume_multiplier=config.spike_volume_multiplier,
                spike_price_move_pct=config.spike_price_move_pct,
                surge_volume_multiplier=config.surge_volume_multiplier,
                surge_requires_price_below_open=config.surge_requires_price_below_open,
                surge_min_gap_minutes=config.surge_min_gap_minutes,
                tranche_count=config.tranche_count,
                hard_stop_pct_below_day1_low=config.hard_stop_pct_below_day1_low,
                max_hold_days=config.max_hold_days,
            )
        )
        self._instruments: dict[str, InstrumentId] = {
            iid: InstrumentId.from_str(iid) for iid in config.instrument_ids
        }
        # Tracks total quantity held per symbol so EXIT_ALL can flatten cleanly.
        # Nautilus's portfolio API can answer this too, but caching avoids the
        # extra call on every minute-bar EXIT decision.
        self._held_qty: dict[str, int] = {iid: 0 for iid in config.instrument_ids}

    def on_start(self) -> None:
        for _iid_str, iid in self._instruments.items():
            self.subscribe_bars(
                BarType(
                    instrument_id=iid,
                    bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
                    aggregation_source=AggregationSource.EXTERNAL,
                )
            )
            self.subscribe_bars(
                BarType(
                    instrument_id=iid,
                    bar_spec=BarSpecification(
                        self._cfg.minute_bar_step, BarAggregation.MINUTE, PriceType.LAST
                    ),
                    aggregation_source=AggregationSource.EXTERNAL,
                )
            )

    def on_bar(self, bar: Bar) -> None:
        symbol_id = str(bar.bar_type.instrument_id)
        ts = datetime.fromtimestamp(bar.ts_event / 1e9, tz=timezone.utc)
        aggregation = bar.bar_type.spec.aggregation

        if aggregation == BarAggregation.DAY:
            intent = self._state_machine.on_daily_bar(
                DailyBar(
                    symbol=symbol_id, ts=ts,
                    open=float(bar.open), high=float(bar.high),
                    low=float(bar.low), close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
        elif aggregation == BarAggregation.MINUTE:
            intent = self._state_machine.on_minute_bar(
                MinuteBar(
                    symbol=symbol_id, ts=ts,
                    open=float(bar.open), high=float(bar.high),
                    low=float(bar.low), close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
        else:
            return

        self._apply_intent(intent, symbol_id)

    def on_stop(self) -> None:
        # Flatten everything on shutdown so backtests close out positions
        # deterministically (matches the Phase 1 toy strategy's convention).
        for symbol_id, qty in list(self._held_qty.items()):
            if qty > 0:
                self._submit(symbol_id, OrderSide.SELL, qty)
                self._held_qty[symbol_id] = 0

    def _apply_intent(self, intent: Intent, symbol_id: str) -> None:
        if intent.kind is IntentKind.NO_OP:
            return
        if intent.kind is IntentKind.ENTER_TRANCHE:
            qty = self._cfg.tranche_size_qty
            self._submit(symbol_id, OrderSide.BUY, qty)
            self._held_qty[symbol_id] += qty
            return
        if intent.kind is IntentKind.EXIT_ALL:
            held = self._held_qty.get(symbol_id, 0)
            if held > 0:
                self._submit(symbol_id, OrderSide.SELL, held)
                self._held_qty[symbol_id] = 0

    def _submit(self, symbol_id: str, side: OrderSide, qty: int) -> None:
        order = self.order_factory.market(
            instrument_id=self._instruments[symbol_id],
            order_side=side,
            quantity=Quantity.from_int(qty),
        )
        self.submit_order(order)
