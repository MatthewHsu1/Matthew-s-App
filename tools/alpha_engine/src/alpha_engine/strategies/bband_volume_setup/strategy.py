"""Nautilus `Strategy` wrapper around the pure BBand+Volume state machine.

Subscribes to msgbus topic `"setup.detected"` at startup. When the scan actor
publishes a setup, this strategy:
  1. Seeds the state machine for the symbol via `seed_setup`.
  2. Dynamically subscribes to the daily + 5-minute bar streams for that
     symbol so the state machine can manage tranches and exits.
  3. On EXIT_ALL, unsubscribes from those streams.

Order sizing is dollar-based: `qty = max(1, int(tranche_dollars / price))`.
Submissions are rejected inline when (a) the estimated fill price is more
than `price_band_pct` away from the latest daily close, or (b) the current
price is below `min_price_usd` (penny-stock guard).
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

from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC, SetupDetected
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
    """Config exposed to env config. State-machine tunables are passed through
    to `BBandVolumeSetupParams`; sizing/risk tunables stay at the strategy."""

    instrument_ids: list[str]
    # Sizing + inline risk.
    tranche_dollars: float = 3000.0
    min_price_usd: float = 10.0
    price_band_pct: float = 5.0
    minute_bar_step: int = 5
    # State-machine tunables (defaults match the v1 strategy spec).
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


def _daily_bar_type(iid: InstrumentId) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def _minute_bar_type(iid: InstrumentId, step: int) -> BarType:
    return BarType(
        instrument_id=iid,
        bar_spec=BarSpecification(step, BarAggregation.MINUTE, PriceType.LAST),
        aggregation_source=AggregationSource.EXTERNAL,
    )


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
        # Instruments are added dynamically on setup detection. Pre-config
        # entries (if any) are accepted for backwards compatibility but
        # NOT subscribed at startup.
        self._instruments: dict[str, InstrumentId] = {
            iid: InstrumentId.from_str(iid) for iid in config.instrument_ids
        }
        self._held_qty: dict[str, int] = {iid: 0 for iid in config.instrument_ids}
        # Latest closes used by price-band check + sizing.
        self._last_daily_close: dict[str, float] = {}
        self._last_minute_close: dict[str, float] = {}

    def on_start(self) -> None:
        self._subscribe_setup_topic(SETUP_DETECTED_TOPIC, self._on_setup_detected)

    def _subscribe_setup_topic(self, topic: str, handler) -> None:
        # Extracted for testability under Cython-sealed Strategy base.
        # Tests can reassign `msgbus` as a MagicMock; this thin seam lets
        # them intercept the subscribe call without patching Cython internals.
        self.msgbus.subscribe(topic=topic, handler=handler)

    def _on_setup_detected(self, msg: SetupDetected) -> None:
        # Register the symbol on first sight (the scan actor can detect a
        # setup for any S&P 500 name — we trust its membership filter).
        symbol_id = msg.symbol
        if symbol_id not in self._instruments:
            self._instruments[symbol_id] = InstrumentId.from_str(symbol_id)
            self._held_qty.setdefault(symbol_id, 0)

        self._state_machine.seed_setup(
            symbol=symbol_id,
            day1_close=msg.day1_close,
            day1_low=msg.day1_low,
            ts=msg.ts,
        )
        # Pre-populate the last-daily-close so the price-band check is
        # immediately usable on the first Day-2 minute bar.
        self._last_daily_close[symbol_id] = msg.day1_close

        iid = self._instruments[symbol_id]
        self.subscribe_bars(_daily_bar_type(iid))
        self.subscribe_bars(_minute_bar_type(iid, self._cfg.minute_bar_step))

    def on_bar(self, bar: Bar) -> None:
        symbol_id = str(bar.bar_type.instrument_id)
        ts = datetime.fromtimestamp(bar.ts_event / 1e9, tz=timezone.utc)
        aggregation = bar.bar_type.spec.aggregation

        if aggregation == BarAggregation.DAY:
            self._last_daily_close[symbol_id] = float(bar.close)
            intent = self._state_machine.on_daily_bar(
                DailyBar(
                    symbol=symbol_id, ts=ts,
                    open=float(bar.open), high=float(bar.high),
                    low=float(bar.low), close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
        elif aggregation == BarAggregation.MINUTE:
            self._last_minute_close[symbol_id] = float(bar.close)
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
        for symbol_id, qty in list(self._held_qty.items()):
            if qty > 0:
                self._submit(symbol_id, OrderSide.SELL, qty)
                self._held_qty[symbol_id] = 0

    def _apply_intent(self, intent: Intent, symbol_id: str) -> None:
        if intent.kind is IntentKind.NO_OP:
            return
        if intent.kind is IntentKind.ENTER_TRANCHE:
            qty = self._size_tranche(symbol_id)
            if qty <= 0:
                return  # _size_tranche logged the reason
            self._submit(symbol_id, OrderSide.BUY, qty)
            self._held_qty[symbol_id] = self._held_qty.get(symbol_id, 0) + qty
            return
        if intent.kind is IntentKind.EXIT_ALL:
            held = self._held_qty.get(symbol_id, 0)
            if held > 0:
                self._submit(symbol_id, OrderSide.SELL, held)
                self._held_qty[symbol_id] = 0
            # Stop consuming bars for this symbol.
            iid = self._instruments.get(symbol_id)
            if iid is not None:
                self.unsubscribe_bars(_daily_bar_type(iid))
                self.unsubscribe_bars(_minute_bar_type(iid, self._cfg.minute_bar_step))

    def _emit_warning(self, message: str) -> None:
        # Thin seam so tests can intercept log.warning without needing a
        # fully-booted Nautilus kernel (self.log is Cython-sealed on Actor).
        self.log.warning(message)

    def _make_market_order(self, instrument_id, order_side: OrderSide, quantity: Quantity):
        # Thin seam over order_factory.market for testability
        # (order_factory is Cython-sealed on Strategy).
        return self.order_factory.market(
            instrument_id=instrument_id,
            order_side=order_side,
            quantity=quantity,
        )

    def _resolve_price(self, symbol_id: str) -> float:
        """Best-available price for sizing/guards. Prefer minute close (live)
        and fall back to last daily close (between sessions / pre-warmup)."""
        return self._last_minute_close.get(symbol_id, self._last_daily_close.get(symbol_id, 0.0))

    def _size_tranche(self, symbol_id: str) -> int:
        price = self._resolve_price(symbol_id)
        if price <= 0:
            self._emit_warning(f"size_skip_no_price: {symbol_id}")
            return 0
        if price < self._cfg.min_price_usd:
            self._emit_warning(f"penny_stock_reject: {symbol_id} price={price:.2f}")
            return 0
        last_daily = self._last_daily_close.get(symbol_id, 0.0)
        if last_daily > 0:
            divergence = abs(price - last_daily) / last_daily * 100.0
            if divergence > self._cfg.price_band_pct:
                self._emit_warning(
                    f"price_band_reject: {symbol_id} divergence={divergence:.2f}pct"
                )
                return 0
        qty = max(1, int(self._cfg.tranche_dollars / price))
        return qty

    def _submit(self, symbol_id: str, side: OrderSide, qty: int) -> None:
        order = self._make_market_order(
            instrument_id=self._instruments[symbol_id],
            order_side=side,
            quantity=Quantity.from_int(qty),
        )
        self.submit_order(order)
