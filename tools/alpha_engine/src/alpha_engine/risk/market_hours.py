from __future__ import annotations

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


def make_market_hours_check(*, market_hours_only: bool) -> PreTradeCheck:
    def check(probe: OrderProbe, ctx: RiskContext) -> Decision:
        if not market_hours_only:
            return Decision.allow()
        
        if ctx.market_open_now:
            return Decision.allow()
        
        return Decision.block(f"market_closed: cannot trade {probe.instrument_id} outside RTH")

    check.name = "market_hours"  # type: ignore[attr-defined]
    return check  # type: ignore[return-value]
