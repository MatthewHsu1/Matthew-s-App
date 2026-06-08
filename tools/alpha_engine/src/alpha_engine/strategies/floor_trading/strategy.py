"""Nautilus Strategy wrapper around the Floor Trading state machine.

Connects three Nautilus event streams to the pure-Python state machine:
  - msgbus topic "setup.detected" -> seed_setup + dynamic subscribe (ticks + bars)
  - TradeTick events -> session-open detection, stop check, spike check
  - Bar events (1-DAY-LAST) -> session-close (days_held + Day-4 default exit)
  - OrderFilled events -> lock T1 stop reference at the realized VWAP fill price

Testable seams (Cython-sealed Nautilus internals each get a thin Python wrapper):
  - _subscribe_setup_topic   wraps msgbus.subscribe
  - _subscribe_ticks         wraps subscribe_trade_ticks
  - _unsubscribe_ticks       wraps unsubscribe_trade_ticks
  - _subscribe_bars          wraps subscribe_bars
  - _unsubscribe_bars        wraps unsubscribe_bars
  - _submit_market_order     wraps order_factory.market + submit_order
  - _log_warning             wraps self.log.warning

The wrapper is feature-complete for backtest. Plan 3 will add the IBKR adapter,
MOC-on-close order type for live Day-4 exits, and async-fill teardown reconciliation.
"""
from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.model.data import Bar, BarSpecification, BarType, TradeTick
from nautilus_trader.model.enums import AggregationSource, BarAggregation, OrderSide, PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy, StrategyConfig

from alpha_engine.scan.setup_detected import SETUP_DETECTED_TOPIC, SetupDetected
from alpha_engine.strategies.floor_trading.params import FloorTradingParams
from alpha_engine.strategies.floor_trading.spike_detector import (
    SpikeDetector,
    SpikeKind,
    TradePrint,
)
from alpha_engine.strategies.floor_trading.state_machine import (
    FloorStateMachine,
    Intent,
    IntentKind,
)


class FloorTradingNautilusParams(StrategyConfig):
    """Config surfaced to env config.

    State-machine tunables pass through to FloorTradingParams; sizing/risk
    tunables stay at the wrapper.
    """

    instrument_ids: list[str]
    # Sizing + inline risk.
    tranche_dollars: float = 5_000.0
    min_price_usd: float = 10.0
    price_band_pct: float = 5.0
    max_concurrent_positions: int = 5
    # State-machine tunables.
    bband_period: int = 20
    bband_stddev: float = 2.0
    volume_avg_period: int = 20
    day1_volume_multiplier: float = 2.0
    burst_window_seconds: float = 5.0
    baseline_window_seconds: float = 120.0
    spike_volume_multiplier: float = 10.0
    stop_pct_below_t1: float = 1.5  # percent
    tranche_count: int = 2
    max_hold_days: int = 3


class FloorTradingStrategy(Strategy):
    """Nautilus Strategy wrapper around the Floor Trading state machine."""

    def __init__(self, config: FloorTradingNautilusParams) -> None:
        super().__init__(config=config)
        self._cfg = config
        params = FloorTradingParams(
            bband_period=config.bband_period,
            bband_stddev=config.bband_stddev,
            volume_avg_period=config.volume_avg_period,
            day1_volume_multiplier=config.day1_volume_multiplier,
            burst_window_seconds=config.burst_window_seconds,
            baseline_window_seconds=config.baseline_window_seconds,
            spike_volume_multiplier=config.spike_volume_multiplier,
            stop_pct_below_t1=config.stop_pct_below_t1,
            tranche_count=config.tranche_count,
            max_hold_days=config.max_hold_days,
        )
        self._state_machine = FloorStateMachine(params)
        self._spike_detector = SpikeDetector(params)
        # Symbol bookkeeping (instrument-id parsing once per registration).
        self._instruments: dict[str, InstrumentId] = {
            iid: InstrumentId.from_str(iid) for iid in config.instrument_ids
        }
        # Position bookkeeping for sizing + EXIT_ALL handling.
        self._held_qty: dict[str, int] = {iid: 0 for iid in config.instrument_ids}
        self._last_price: dict[str, float] = {}
        self._day1_close_ref: dict[str, float] = {}  # seeded to day1_close on SetupDetected
        self._last_session_date: dict[str, str] = {}  # populated on first RTH tick per symbol

    def on_start(self) -> None:
        self._subscribe_setup_topic(SETUP_DETECTED_TOPIC, self._on_setup_detected)

    # ----- Testable seams -----

    def _subscribe_setup_topic(self, topic: str, handler) -> None:
        """Thin seam over msgbus.subscribe so tests can intercept without
        patching Cython-sealed msgbus attribute.
        """
        self.msgbus.subscribe(topic=topic, handler=handler)

    def _subscribe_ticks(self, iid: InstrumentId) -> None:
        """Thin seam over subscribe_trade_ticks.

        subscribe_trade_ticks is a Cython method on Actor. Tests patch this
        seam via patch.object(strat, "_subscribe_ticks") so they can assert
        the subscription call without a live Nautilus kernel.
        """
        self.subscribe_trade_ticks(iid)

    def _on_setup_detected(self, msg: SetupDetected) -> None:
        symbol_id = msg.symbol
        if symbol_id not in self._instruments:
            self._instruments[symbol_id] = InstrumentId.from_str(symbol_id)
            self._held_qty.setdefault(symbol_id, 0)
        # Concurrency cap: skip seeding new symbols when at capacity.
        # "active" = capital deployed (held_qty > 0). Symbols in SETUP_DETECTED /
        # DAY2_PRE_ENTRY have no fill yet; they do not count against the cap.
        active = sum(1 for q in self._held_qty.values() if q > 0)
        if active >= self._cfg.max_concurrent_positions:
            return
        self._state_machine.seed_setup(
            symbol=symbol_id,
            day1_close=msg.day1_close,
            day1_low=msg.day1_low,
            ts=msg.ts,
        )
        self._last_price[symbol_id] = msg.day1_close
        self._day1_close_ref[symbol_id] = msg.day1_close
        self._subscribe_ticks(self._instruments[symbol_id])
        self._subscribe_bars(self._daily_bar_type(symbol_id))

    # ----- Tick + intent handling (Task 11) -----

    def on_trade_tick(self, tick: TradeTick) -> None:
        """Process a trade-print event from the venue/sim.

        Order of checks: RTH gate -> session-open (on first tick of day) ->
        stop-loss -> spike. Each layer can emit an Intent that gets applied
        immediately.
        """
        symbol_id = str(tick.instrument_id)
        ts = datetime.fromtimestamp(tick.ts_event / 1e9, tz=timezone.utc)
        price = float(tick.price)
        if not self._in_rth(ts):
            return
        self._last_price[symbol_id] = price

        # 1. First RTH tick of the session -> on_session_open gate.
        session_key = ts.strftime("%Y-%m-%d")
        if self._last_session_date.get(symbol_id) != session_key:
            self._last_session_date[symbol_id] = session_key
            open_intent = self._state_machine.on_session_open(
                symbol=symbol_id, open_price=price, ts=ts,
            )
            self._apply_intent(open_intent, symbol_id, price)

        # 2. Stop check. Stop > TP priority means we evaluate the stop here
        # BEFORE the spike detector. If the stop fires, return early so a
        # same-tick up-spike cannot accidentally override the exit reason.
        # (Session-open is a one-shot daily transition, not an exit -- it
        # runs first regardless of priority.)
        stop_intent = self._state_machine.on_print_for_stop(
            symbol=symbol_id, print_price=price, ts=ts,
        )
        if stop_intent.kind is not IntentKind.NO_OP:
            self._apply_intent(stop_intent, symbol_id, price)
            return

        # 3. Spike check.
        spike = self._spike_detector.on_print(
            TradePrint(symbol=symbol_id, ts=ts, price=price, size=float(tick.size))
        )
        if spike.kind is SpikeKind.NONE:
            return
        spike_intent = self._state_machine.on_spike(
            symbol=symbol_id, kind_down=(spike.kind is SpikeKind.DOWN),
            spike_price=spike.burst_vwap, ts=ts,
        )
        self._apply_intent(spike_intent, symbol_id, price)

    def _daily_bar_type(self, symbol_id: str) -> BarType:
        return BarType(
            instrument_id=self._instruments[symbol_id],
            bar_spec=BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
            aggregation_source=AggregationSource.EXTERNAL,
        )

    def on_bar(self, bar: Bar) -> None:
        """Process a closed daily bar -- drives state-machine day-counting + Day-4 close.

        Ignores non-DAY aggregations (the actor + this wrapper only subscribe
        to 1-DAY bars; defensive filter against unexpected emissions).
        """
        if bar.bar_type.spec.aggregation != BarAggregation.DAY:
            return
        symbol_id = str(bar.bar_type.instrument_id)
        ts = datetime.fromtimestamp(bar.ts_event / 1e9, tz=timezone.utc)
        intent = self._state_machine.on_session_close(
            symbol=symbol_id,
            day_close=float(bar.close), day_open=float(bar.open),
            day_high=float(bar.high), day_low=float(bar.low),
            day_volume=float(bar.volume), ts=ts,
        )
        # Use the daily-bar close as the price reference for exit sizing
        # (Day-4 default close exits at the day's close per spec).
        self._apply_intent(intent, symbol_id, float(bar.close))

    @staticmethod
    def _in_rth(ts: datetime) -> bool:
        """RTH window check.

        Bounds: 13:30 UTC <= ts < 20:00 UTC matches RTH in DST (Mar-Nov).
        For EST (Nov-Mar) the actual open is 14:30 UTC -- the wider DST
        bounds admit ~30 min of pre-market in winter, which is harmless
        since the catalog and live IBKR both only publish RTH ticks anyway.
        Holidays not modeled here.
        """
        hour = ts.hour
        minute = ts.minute
        before_open = hour < 13 or (hour == 13 and minute < 30)
        after_close = hour >= 20
        return not before_open and not after_close

    def _apply_intent(self, intent: Intent, symbol_id: str, current_price: float) -> None:
        if intent.kind is IntentKind.NO_OP:
            return
        if intent.kind is IntentKind.ENTER_TRANCHE:
            qty = self._size_tranche(symbol_id, current_price)
            if qty <= 0:
                return
            self._submit_market_order(symbol_id=symbol_id, side=OrderSide.BUY, qty=qty)
            self._held_qty[symbol_id] = self._held_qty.get(symbol_id, 0) + qty
            return
        if intent.kind is IntentKind.EXIT_ALL:
            held = self._held_qty.get(symbol_id, 0)
            if held > 0:
                self._submit_market_order(symbol_id=symbol_id, side=OrderSide.SELL, qty=held)
                self._held_qty[symbol_id] = 0
            # NOTE(plan-3): teardown (unsubscribe + on_setup_complete + session
            # date pop) runs synchronously here, BEFORE the SELL order fills.
            # In backtest this is correct (market orders fill synchronously),
            # but for paper/live this could race: on_order_filled for the SELL
            # may arrive after the book has already been reset to IDLE, and
            # on_t1_filled would silently skip due to its state guard.
            # Plan 3 (live wiring) will move this teardown into on_order_filled's
            # SELL branch.
            iid = self._instruments.get(symbol_id)
            if iid is not None:
                self._unsubscribe_ticks(iid)
                self._unsubscribe_bars(self._daily_bar_type(symbol_id))
            self._state_machine.on_setup_complete(symbol_id)
            self._last_session_date.pop(symbol_id, None)

    def _size_tranche(self, symbol_id: str, current_price: float) -> int:
        if current_price <= 0.0:
            return 0
        if current_price < self._cfg.min_price_usd:
            self._log_warning(f"penny_stock_reject: {symbol_id} price={current_price:.2f}")
            return 0
        # Price-band guard: refuse to size if the entry print is too far from
        # the Day-1 close reference (defends against catastrophic gap-down
        # entries that would print well below the thesis level).
        reference = self._day1_close_ref.get(symbol_id, 0.0)
        if reference > 0.0:
            divergence_pct = abs(current_price - reference) / reference * 100.0
            if divergence_pct > self._cfg.price_band_pct:
                self._log_warning(
                    f"price_band_reject: {symbol_id} divergence={divergence_pct:.2f}pct"
                )
                return 0
        return max(1, int(self._cfg.tranche_dollars / current_price))

    # ----- Cython-sealed seams -----

    def _submit_market_order(self, *, symbol_id: str, side: OrderSide, qty: int) -> None:
        """Thin seam over order_factory.market + submit_order for testability.

        order_factory and submit_order are Cython methods on Actor/Strategy.
        Tests patch this seam via patch.object so they can assert order
        submissions without needing a live Nautilus kernel.
        """
        order = self.order_factory.market(
            instrument_id=self._instruments[symbol_id],
            order_side=side,
            quantity=Quantity.from_int(qty),
        )
        self.submit_order(order)

    def _unsubscribe_ticks(self, iid: InstrumentId) -> None:
        """Thin seam over unsubscribe_trade_ticks for testability.

        unsubscribe_trade_ticks is a Cython method on Actor. Tests patch this
        seam so tick-unsubscription can be asserted without a live kernel.
        """
        self.unsubscribe_trade_ticks(iid)

    def _subscribe_bars(self, bar_type: BarType) -> None:
        """Thin seam over self.subscribe_bars (Cython-sealed Actor method)."""
        self.subscribe_bars(bar_type)

    def _unsubscribe_bars(self, bar_type: BarType) -> None:
        """Thin seam over self.unsubscribe_bars (Cython-sealed Actor method)."""
        self.unsubscribe_bars(bar_type)

    def _log_warning(self, message: str) -> None:
        """Thin seam over self.log.warning for testability.

        self.log is a Cython-sealed attribute; its .warning method cannot be
        patched directly. Tests patch this seam instead.
        """
        self.log.warning(message)

    def on_order_filled(self, event) -> None:  # type: ignore[override]
        """On fill of a T1 buy order, lock the stop reference at the actual fill price.

        Nautilus calls this with an OrderFilled event. The state machine's
        on_t1_filled records the avg fill price into the book so the stop
        check uses the realized VWAP instead of the intent emission price.
        """
        symbol_id = str(event.instrument_id)
        ts = datetime.fromtimestamp(event.ts_event / 1e9, tz=timezone.utc)
        if event.order_side == OrderSide.BUY:
            book = self._state_machine._books.get(symbol_id)
            # Only the FIRST BUY (T1) locks the stop reference. T2 BUY fills
            # arrive later but their last_px is intentionally NOT recorded --
            # the stop is locked at T1's fill price by spec (see ADR-0002),
            # not the blended cost basis.
            if book is not None and book.t1_fill_price == 0.0:
                self._state_machine.on_t1_filled(
                    symbol=symbol_id, fill_price=float(event.last_px), ts=ts,
                )
