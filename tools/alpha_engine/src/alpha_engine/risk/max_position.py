from __future__ import annotations

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


def make_max_position_check(*, max_usd: float) -> PreTradeCheck:
    if max_usd <= 0:
        raise ValueError("max_usd must be > 0")

    def check(probe: OrderProbe, ctx: RiskContext) -> Decision:
        if probe.side == "SELL":
            return Decision.allow()
        
        existing = ctx.position_usd(probe.instrument_id)
        projected = existing + probe.notional_usd()
        
        if projected > max_usd:
            return Decision.block(
                f"max_position exceeded: projected ${projected:,.2f} > cap ${max_usd:,.2f}"
            )
        
        return Decision.allow()

    check.name = "max_position"  # type: ignore[attr-defined]
    return check  # type: ignore[return-value]
