from __future__ import annotations

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


def make_price_band_check(*, max_bps: int) -> PreTradeCheck:
    if max_bps <= 0:
        raise ValueError("max_bps must be > 0")
    threshold = max_bps / 10_000.0

    def check(probe: OrderProbe, ctx: RiskContext) -> Decision:
        if probe.limit_price is None:
            return Decision.allow()
        
        quote = ctx.last_quote.get(probe.instrument_id)

        if quote is None or quote <= 0:
            return Decision.block(
                f"price_band: no_quote for {probe.instrument_id}; cannot validate fat-finger"
            )
        
        deviation = abs(probe.limit_price - quote) / quote

        if deviation > threshold:
            return Decision.block(
                f"price_band exceeded: limit ${probe.limit_price:.4f} deviates "
                f"{deviation * 10_000:.1f} bps from quote ${quote:.4f} (cap {max_bps} bps)"
            )
        
        return Decision.allow()

    check.name = "price_band"  # type: ignore[attr-defined]
    return check  # type: ignore[return-value]
