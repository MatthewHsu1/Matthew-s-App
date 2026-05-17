from __future__ import annotations

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


def make_max_daily_loss_check(*, max_loss_usd: float) -> PreTradeCheck:
    if max_loss_usd <= 0:
        raise ValueError("max_loss_usd must be > 0")

    def check(probe: OrderProbe, ctx: RiskContext) -> Decision:
        total = ctx.realized_pnl_usd_today + ctx.unrealized_pnl_usd

        if total <= -abs(max_loss_usd):
            return Decision.block(
                f"max_daily_loss exceeded: total ${total:,.2f} <= -${max_loss_usd:,.2f}"
            )
        
        return Decision.allow()

    check.name = "max_daily_loss"  # type: ignore[attr-defined]
    return check  # type: ignore[return-value]
