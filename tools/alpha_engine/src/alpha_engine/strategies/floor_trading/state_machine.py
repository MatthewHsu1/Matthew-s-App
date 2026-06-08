"""Floor Trading state machine.

Pure Python -- no Nautilus. The Nautilus wrapper translates bar/tick events
into the typed inputs here and translates emitted ``Intent`` values back
into order submissions.

States:
  IDLE              -- nothing of interest
  SETUP_DETECTED    -- Day-1 rule fired; awaiting Day 2's open-rule check
  DAY2_PRE_ENTRY    -- Day 2 opened red; armed for down-spike (T1 entry)
  HOLDING_T1        -- T1 fill confirmed; stop active; can scale to T2 on Day 3
  DAY3_PRE_ADD      -- Day 3 opened red; armed for T2 down-spike
  HOLDING_T1_T2     -- T2 fill confirmed; stop unchanged (locked at T1 fill)
  DAY4_HOLDING      -- Day 4 in progress; exit on stop, TP, or default close
  EXITED            -- position closed (terminal until next IDLE re-arm)

Tasks 4-7 built this incrementally. After Task 7 the state machine is
complete: it handles all 8 states (IDLE, SETUP_DETECTED, DAY2_PRE_ENTRY,
HOLDING_T1, DAY3_PRE_ADD, HOLDING_T1_T2, DAY4_HOLDING, EXITED) plus the
on_print_for_stop hook and the on_setup_complete re-arm callback.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from alpha_engine.strategies.floor_trading.params import FloorTradingParams

__all__ = [
    "DailyBar",
    "FloorStateMachine",
    "Intent",
    "IntentKind",
    "SymbolState",
]


class SymbolState(Enum):
    IDLE = auto()
    SETUP_DETECTED = auto()
    DAY2_PRE_ENTRY = auto()
    HOLDING_T1 = auto()
    DAY3_PRE_ADD = auto()
    HOLDING_T1_T2 = auto()
    DAY4_HOLDING = auto()
    EXITED = auto()


class IntentKind(Enum):
    NO_OP = auto()
    ENTER_TRANCHE = auto()
    EXIT_ALL = auto()


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    symbol: str = ""
    tranche_index: int = 0  # 1 or 2
    reason: str = ""

    @classmethod
    def no_op(cls) -> Intent:
        return cls(kind=IntentKind.NO_OP)


@dataclass(frozen=True)
class DailyBar:
    """Daily OHLCV bar emitted at session close (16:00 ET)."""

    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class _Book:
    state: SymbolState = SymbolState.IDLE
    day1_close: float = 0.0
    # day1_low: retained for downstream consumers (audit log, future
    # hard-stop variant). Floor Trading's stop uses t1_fill_price, not
    # day1_low -- this field is set but never read inside the state machine.
    day1_low: float = 0.0
    day2_close: float = 0.0
    t1_fill_price: float = 0.0
    t1_fill_ts: datetime | None = None
    # Bookkeeping for daily-bar progression (built out in Tasks 5-7).
    days_held: int = 0


class FloorStateMachine:
    def __init__(self, params: FloorTradingParams) -> None:
        self._params = params
        self._books: dict[str, _Book] = {}

    def state_of(self, symbol: str) -> SymbolState:
        return self._books.get(symbol, _Book()).state

    def seed_setup(
        self,
        *,
        symbol: str,
        day1_close: float,
        day1_low: float,
        ts: datetime,
    ) -> None:
        """External transition IDLE -> SETUP_DETECTED (or re-seed when already there).

        Called by the Nautilus wrapper on receipt of a SetupDetected event
        from FloorScanActor. Idempotent in SETUP_DETECTED. No-op when the
        book is past SETUP_DETECTED (position in flight).
        """
        book = self._books.setdefault(symbol, _Book())

        if book.state not in (SymbolState.IDLE, SymbolState.SETUP_DETECTED):
            return
        
        book.state = SymbolState.SETUP_DETECTED
        book.day1_close = day1_close
        book.day1_low = day1_low

    def on_session_open(self, *, symbol: str, open_price: float, ts: datetime) -> Intent:
        """First RTH print of the day -- evaluate gates that depend on the open."""
        book = self._books.get(symbol)

        if book is None:
            return Intent.no_op()
        
        if book.state is SymbolState.SETUP_DETECTED:
            return self._handle_day2_open(book, symbol, open_price, ts)
        
        if book.state is SymbolState.HOLDING_T1:
            return self._handle_day3_open(book, symbol, open_price, ts)
        
        # DAY4_HOLDING + HOLDING_T1_T2 do not gate on open -- exits are intraday-only.
        return Intent.no_op()

    def _handle_day2_open(self, book: _Book, symbol: str, open_price: float, ts: datetime) -> Intent:
        # Spec: today's open MUST be strictly less than Day-1 close.
        if open_price >= book.day1_close:
            self._reset_to_idle(book)
            return Intent.no_op()

        book.state = SymbolState.DAY2_PRE_ENTRY

        return Intent.no_op()

    def _handle_day3_open(self, book: _Book, symbol: str, open_price: float, ts: datetime) -> Intent:
        # Spec: open MUST be strictly less than Day-2 close to add T2.
        if open_price >= book.day2_close:
            # Skip T2; remain HOLDING_T1.
            return Intent.no_op()
        
        book.state = SymbolState.DAY3_PRE_ADD

        return Intent.no_op()

    def on_spike(self, *, symbol: str, kind_down: bool, spike_price: float, ts: datetime) -> Intent:
        """A spike of kind DOWN or UP fired for `symbol` during RTH."""
        book = self._books.get(symbol)

        if book is None:
            return Intent.no_op()
        
        if book.state is SymbolState.DAY2_PRE_ENTRY:
            return self._handle_day2_spike(book, symbol, kind_down)
        
        if book.state is SymbolState.DAY3_PRE_ADD:
            return self._handle_day3_pre_add_spike(book, symbol, kind_down)
        
        if book.state in (
            SymbolState.HOLDING_T1,
            SymbolState.HOLDING_T1_T2,
            SymbolState.DAY4_HOLDING,
        ):
            # TP exit on up-spike; down-spike ignored (no further scaling).
            if not kind_down:
                book.state = SymbolState.EXITED
                return Intent(kind=IntentKind.EXIT_ALL, symbol=symbol, reason="take_profit")
            return Intent.no_op()

        return Intent.no_op()

    def _handle_day2_spike(self, book: _Book, symbol: str, kind_down: bool) -> Intent:
        if kind_down:
            book.state = SymbolState.HOLDING_T1
            return Intent(kind=IntentKind.ENTER_TRANCHE, symbol=symbol, tranche_index=1)

        # Up-spike before entry => abandon (setup invalidated).
        self._reset_to_idle(book)

        return Intent.no_op()

    def _handle_day3_pre_add_spike(self, book: _Book, symbol: str, kind_down: bool) -> Intent:
        if kind_down:
            book.state = SymbolState.HOLDING_T1_T2
            return Intent(kind=IntentKind.ENTER_TRANCHE, symbol=symbol, tranche_index=2)
        
        # Up-spike on Day-3 => take profit, exit immediately.
        book.state = SymbolState.EXITED
        return Intent(kind=IntentKind.EXIT_ALL, symbol=symbol, reason="take_profit")

    def on_session_close(
        self,
        *,
        symbol: str,
        day_close: float,
        day_open: float,
        day_high: float,
        day_low: float,
        day_volume: float,
        ts: datetime,
    ) -> Intent:
        """Session-close event (16:00 ET). Drives day-counting, DAY2/3 timeouts,
        and Day-4 default close.
        """
        book = self._books.get(symbol)

        if book is None:
            return Intent.no_op()
        
        if book.state is SymbolState.DAY2_PRE_ENTRY:
            self._reset_to_idle(book)
            return Intent.no_op()

        if book.state is SymbolState.DAY4_HOLDING:
            # Neither stop nor TP fired during Day 4; default close.
            book.state = SymbolState.EXITED
            return Intent(kind=IntentKind.EXIT_ALL, symbol=symbol, reason="default_close")

        if book.state in (SymbolState.HOLDING_T1, SymbolState.HOLDING_T1_T2, SymbolState.DAY3_PRE_ADD):
            # First close after T1 fill = end of Day 2 -- record Day-2's close so
            # Day-3's open-rule has its reference. days_held tracks how many
            # sessions have closed since T1 fill.
            if book.day2_close == 0.0:
                book.day2_close = day_close
                book.days_held = 1
                return Intent.no_op()

            book.days_held += 1

            if book.state is SymbolState.DAY3_PRE_ADD:
                # No T2 spike all day -- revert to HOLDING_T1.
                book.state = SymbolState.HOLDING_T1

            if book.days_held >= 2:
                # Day-3 just closed; next session is Day 4.
                book.state = SymbolState.DAY4_HOLDING

            return Intent.no_op()

        return Intent.no_op()

    def on_t1_filled(self, *, symbol: str, fill_price: float, ts: datetime) -> None:
        """Confirmation from the venue/sim that Tranche 1 has filled.

        The Nautilus wrapper calls this on `on_order_filled` for the T1 order
        so the state machine can lock the stop reference at the actual VWAP
        fill price (not the intent emission price).
        """
        book = self._books.get(symbol)

        if book is None:
            return
        
        if book.state is not SymbolState.HOLDING_T1:
            return
        
        book.t1_fill_price = fill_price
        book.t1_fill_ts = ts

    def on_print_for_stop(self, *, symbol: str, print_price: float, ts: datetime) -> Intent:
        """Evaluate the stop-loss against the latest trade-print price.

        Called by the Nautilus wrapper on every RTH trade-print for a symbol
        in a holding state, BEFORE the spike detector runs. Stop > TP priority
        is enforced here: if stop fires, the spike-event handler will see an
        EXITED book and return NO_OP.
        """
        book = self._books.get(symbol)

        if book is None:
            return Intent.no_op()
        
        if book.state not in (
            SymbolState.HOLDING_T1,
            SymbolState.HOLDING_T1_T2,
            SymbolState.DAY3_PRE_ADD,
            SymbolState.DAY4_HOLDING,
        ):
            return Intent.no_op()
        
        if book.t1_fill_price <= 0.0:
            return Intent.no_op()
        
        stop_level = book.t1_fill_price * (1.0 - self._params.stop_pct_below_t1 / 100.0)

        if print_price <= stop_level:
            book.state = SymbolState.EXITED
            return Intent(kind=IntentKind.EXIT_ALL, symbol=symbol, reason="stop_loss")
        
        return Intent.no_op()

    def on_setup_complete(self, symbol: str) -> None:
        """Called by the wrapper once the EXIT_ALL order has been filled.

        Resets the symbol's book to IDLE so a fresh Day-1 detection can re-arm
        the symbol. Separated from the EXITED transition because the wrapper
        needs the EXITED state to know it still has an outstanding exit order.
        """
        book = self._books.get(symbol)

        if book is None:
            return
        
        if book.state is not SymbolState.EXITED:
            return
        
        self._reset_to_idle(book)

    def _reset_to_idle(self, book: _Book) -> None:
        book.state = SymbolState.IDLE
        book.day1_close = 0.0
        book.day1_low = 0.0
        book.day2_close = 0.0
        book.t1_fill_price = 0.0
        book.t1_fill_ts = None
        book.days_held = 0

    # Test-only seam -- lets unit tests jump to mid-flow states without
    # building up the full transition history. Marked private so production
    # code does not accidentally use it.
    def _force_state_for_test(self, symbol: str, state: SymbolState) -> None:
        self._books.setdefault(symbol, _Book()).state = state
