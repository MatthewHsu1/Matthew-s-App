"""Pure-Python state machine for the BBand + volume setup strategy.

Nautilus-free so it can be unit-tested with synthetic bars in milliseconds.
The Nautilus `Strategy` wrapper translates bar events into the typed inputs
here and translates emitted `Intent` values back into order submissions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from alpha_engine.strategies.bband_volume_setup.detection import (
    Day1Inputs,
    is_day1_setup,
)
from alpha_engine.strategies.bband_volume_setup.params import (
    BBandVolumeSetupParams,
)

__all__ = [
    "BBandVolumeSetupParams",
    "BBandVolumeSetupStateMachine",
    "DailyBar",
    "Intent",
    "IntentKind",
    "MinuteBar",
    "SymbolState",
]


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class MinuteBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class SymbolState(Enum):
    IDLE = auto()
    SETUP_DETECTED = auto()
    DAY2_ACTIVE = auto()
    DAY3_SCALING = auto()
    DAY4_OBSERVE = auto()
    DAY5_FINAL = auto()
    EXITED = auto()


class IntentKind(Enum):
    NO_OP = auto()
    ENTER_TRANCHE = auto()
    EXIT_ALL = auto()


@dataclass(frozen=True)
class Intent:
    kind: IntentKind
    symbol: str = ""
    tranche_index: int = 0
    reason: str = ""

    @classmethod
    def no_op(cls) -> Intent:
        return cls(kind=IntentKind.NO_OP)


@dataclass
class _SymbolBook:
    state: SymbolState = SymbolState.IDLE
    closes: deque[float] = field(default_factory=deque)
    volumes: deque[float] = field(default_factory=deque)
    day1_close: float = 0.0
    day1_low: float = 0.0
    tranches_filled: int = 0
    # Per-session intraday tracking.
    current_session_open: float = 0.0
    minute_volumes: deque[float] = field(default_factory=deque)
    last_surge_ts: datetime | None = None


class BBandVolumeSetupStateMachine:
    def __init__(self, params: BBandVolumeSetupParams) -> None:
        self._params = params
        self._books: dict[str, _SymbolBook] = {}

    def state_of(self, symbol: str) -> SymbolState:
        return self._books.get(symbol, _SymbolBook()).state

    def on_daily_bar(self, bar: DailyBar) -> Intent:
        book = self._books.setdefault(bar.symbol, _SymbolBook())

        # Evaluate transitions against the rolling window BEFORE appending today's
        # bar, so today's close/volume do not contaminate the baseline.
        intent = self._handle_daily(book, bar)

        book.closes.append(bar.close)
        book.volumes.append(bar.volume)
        if len(book.closes) > self._params.bband_period:
            book.closes.popleft()
        if len(book.volumes) > self._params.volume_avg_period:
            book.volumes.popleft()

        return intent

    def _handle_daily(self, book: _SymbolBook, bar: DailyBar) -> Intent:
        if book.state is SymbolState.IDLE:
            return self._maybe_detect_setup(book, bar)
        if book.state is SymbolState.SETUP_DETECTED:
            return self._handle_day2(book, bar)
        # Day 5 has elapsed by the time Day 6's bar arrives. Nautilus does
        # not emit explicit session-close events, so the next daily bar after
        # DAY5_FINAL is the session-end trigger for max_hold exits.
        if book.state is SymbolState.DAY5_FINAL:
            book.state = SymbolState.EXITED
            return Intent(
                kind=IntentKind.EXIT_ALL, symbol=bar.symbol, reason="max_hold_days"
            )
        # In-position day advance: each new daily bar advances the day counter.
        next_state = {
            SymbolState.DAY2_ACTIVE: SymbolState.DAY3_SCALING,
            SymbolState.DAY3_SCALING: SymbolState.DAY4_OBSERVE,
            SymbolState.DAY4_OBSERVE: SymbolState.DAY5_FINAL,
        }.get(book.state)
        if next_state is not None:
            book.state = next_state
            book.current_session_open = bar.open
            book.minute_volumes.clear()
            book.last_surge_ts = None
        return Intent.no_op()

    def _maybe_detect_setup(self, book: _SymbolBook, bar: DailyBar) -> Intent:
        inputs = Day1Inputs(
            prior_closes=list(book.closes),
            prior_volumes=list(book.volumes),
            bar_low=bar.low,
            bar_volume=bar.volume,
        )
        if is_day1_setup(inputs, self._params):
            book.state = SymbolState.SETUP_DETECTED
            book.day1_close = bar.close
            book.day1_low = bar.low
        return Intent.no_op()

    def _handle_day2(self, book: _SymbolBook, bar: DailyBar) -> Intent:
        # "Opens green" = open above prior day's close. A flat or down open
        # invalidates the thesis ("don't chase").
        if bar.open <= book.day1_close:
            self._reset(book)
            return Intent.no_op()
        book.state = SymbolState.DAY2_ACTIVE
        book.tranches_filled = 1
        book.current_session_open = bar.open
        book.minute_volumes.clear()
        book.last_surge_ts = None
        return Intent(
            kind=IntentKind.ENTER_TRANCHE,
            symbol=bar.symbol,
            tranche_index=1,
        )

    def on_minute_bar(self, bar: MinuteBar) -> Intent:
        book = self._books.get(bar.symbol)
        if book is None or book.state in (
            SymbolState.IDLE,
            SymbolState.SETUP_DETECTED,
            SymbolState.EXITED,
        ):
            return Intent.no_op()

        # Hard stop trumps every other intraday rule.
        stop_price = book.day1_low * (1.0 - self._params.hard_stop_pct_below_day1_low / 100.0)
        if bar.low <= stop_price:
            book.state = SymbolState.EXITED
            return Intent(kind=IntentKind.EXIT_ALL, symbol=bar.symbol, reason="hard_stop")

        avg_volume = (
            sum(book.minute_volumes) / len(book.minute_volumes)
            if book.minute_volumes
            else 0.0
        )
        book.minute_volumes.append(bar.volume)
        if len(book.minute_volumes) > self._params.volume_avg_period:
            book.minute_volumes.popleft()

        # Need a full baseline before any volume-relative trigger fires.
        # `<=` on the length check: we just appended, so the bar we're evaluating is the (N+1)th.
        if avg_volume <= 0.0 or len(book.minute_volumes) <= self._params.volume_avg_period:  # noqa: SIM102
            if avg_volume <= 0.0:
                return Intent.no_op()

        if book.state is SymbolState.DAY2_ACTIVE:
            return self._maybe_spike(book, bar, avg_volume)
        if book.state is SymbolState.DAY3_SCALING:
            return self._maybe_surge(book, bar, avg_volume)
        # Day 4 / Day 5: hold and observe; exits driven by session close.
        return Intent.no_op()

    def _maybe_spike(self, book: _SymbolBook, bar: MinuteBar, avg_volume: float) -> Intent:
        volume_trigger = bar.volume >= self._params.spike_volume_multiplier * avg_volume
        if book.current_session_open <= 0:
            return Intent.no_op()
        price_move_pct = (bar.high - book.current_session_open) / book.current_session_open * 100.0
        price_trigger = price_move_pct >= self._params.spike_price_move_pct
        if volume_trigger and price_trigger:
            book.state = SymbolState.EXITED
            return Intent(kind=IntentKind.EXIT_ALL, symbol=bar.symbol, reason="day2_spike")
        return Intent.no_op()

    def _maybe_surge(self, book: _SymbolBook, bar: MinuteBar, avg_volume: float) -> Intent:
        if book.tranches_filled >= self._params.tranche_count:
            return Intent.no_op()
        volume_trigger = bar.volume >= self._params.surge_volume_multiplier * avg_volume
        if not volume_trigger:
            return Intent.no_op()
        if self._params.surge_requires_price_below_open and bar.close > book.current_session_open:
            return Intent.no_op()
        if book.last_surge_ts is not None:
            gap = (bar.ts - book.last_surge_ts).total_seconds() / 60.0
            if gap < self._params.surge_min_gap_minutes:
                return Intent.no_op()
        book.tranches_filled += 1
        book.last_surge_ts = bar.ts
        return Intent(
            kind=IntentKind.ENTER_TRANCHE,
            symbol=bar.symbol,
            tranche_index=book.tranches_filled,
        )

    def on_session_close(self, symbol: str) -> Intent:
        book = self._books.get(symbol)
        if book is None:
            return Intent.no_op()
        if book.state is SymbolState.DAY5_FINAL:
            book.state = SymbolState.EXITED
            return Intent(kind=IntentKind.EXIT_ALL, symbol=symbol, reason="max_hold_days")
        return Intent.no_op()

    def _reset(self, book: _SymbolBook) -> None:
        book.state = SymbolState.IDLE
        book.day1_close = 0.0
        book.day1_low = 0.0
        book.tranches_filled = 0
        book.current_session_open = 0.0
        book.minute_volumes.clear()
        book.last_surge_ts = None
