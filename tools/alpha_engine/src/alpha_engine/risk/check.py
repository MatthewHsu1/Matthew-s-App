from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from alpha_engine.contracts.decision import Decision


@dataclass(frozen=True)
class OrderProbe:
    """The minimal order info every risk check needs."""

    instrument_id: str
    side: str  # "BUY" | "SELL"
    quantity: float
    limit_price: float | None  # None for market orders

    def notional_usd(self) -> float:
        # Phase 1: USD-denominated equities. Refine when other ccys arrive.
        if self.limit_price is None:
            raise ValueError("notional requires limit_price; pass last quote for market orders")
        
        return abs(self.quantity * self.limit_price)


@dataclass(frozen=True)
class RiskContext:
    positions_usd: dict[str, float] = field(default_factory=dict)
    last_quote: dict[str, float] = field(default_factory=dict)
    realized_pnl_usd_today: float = 0.0
    unrealized_pnl_usd: float = 0.0
    now_local: datetime | None = None
    market_open_now: bool = True

    def position_usd(self, instrument_id: str) -> float:
        return self.positions_usd.get(instrument_id, 0.0)


class PreTradeCheck(Protocol):
    name: str

    def __call__(self, probe: OrderProbe, ctx: RiskContext) -> Decision: ...
