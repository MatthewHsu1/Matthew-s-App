"""OrderGate: pure decision layer + Actor wrapper.

The pure layer (`gate_decision`) is what unit tests exercise. The Actor wrapper
(`AlphaOrderGate`) is wired into the Nautilus msgbus in Task 22.

Fail-closed semantics: if any check raises, the gate blocks with reason
'gate_internal_error'. Better to block than let an unchecked order through.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


@dataclass(frozen=True)
class GateOutcome:
    allowed: bool
    blocking_check: str | None
    reason: str | None
    decisions: list[tuple[str, Decision]] = field(default_factory=list)


def gate_decision(
    probe: OrderProbe,
    ctx: RiskContext,
    checks: Sequence[PreTradeCheck],
) -> GateOutcome:
    """Run pre-trade checks in order. First block wins. Errors fail closed."""
    decisions: list[tuple[str, Decision]] = []
    for check in checks:
        try:
            d = check(probe, ctx)
        except Exception:
            return GateOutcome(
                allowed=False,
                blocking_check=getattr(check, "name", check.__class__.__name__),
                reason="gate_internal_error",
                decisions=decisions,
            )
        decisions.append((getattr(check, "name", check.__class__.__name__), d))
        if not d.allowed:
            return GateOutcome(
                allowed=False,
                blocking_check=getattr(check, "name", check.__class__.__name__),
                reason=d.reason,
                decisions=decisions,
            )
    return GateOutcome(allowed=True, blocking_check=None, reason=None, decisions=decisions)


SUBMIT_ORDER_TOPIC = "commands.trading.submit_order"
ORDER_DENIED_TOPIC = "events.order.denied"


class AlphaOrderGate:
    """Wraps `gate_decision` and binds it to the Nautilus message bus.

    Not a Nautilus Actor subclass — Nautilus's Actor base imports a lot. We
    use duck typing: any object with `subscribe(topic, handler)` works as
    msgbus, and the gate is registered manually from engine/paper.py.
    """

    def __init__(
        self,
        *,
        msgbus,
        risk_logger,
        checks: Sequence[PreTradeCheck],
        context_provider: Callable[[], RiskContext],
    ):
        self._msgbus = msgbus
        self._risk_logger = risk_logger
        self._checks = list(checks)
        self._context_provider = context_provider

    def on_start(self) -> None:
        self._msgbus.subscribe(topic=SUBMIT_ORDER_TOPIC, handler=self._on_submit_order)

    def _on_submit_order(self, cmd) -> None:
        probe = OrderProbe(
            instrument_id=str(cmd.instrument_id),
            side=str(cmd.side),
            quantity=float(cmd.quantity),
            limit_price=float(cmd.limit_price) if cmd.limit_price is not None else None,
        )
        
        ctx = self._context_provider()
        outcome = gate_decision(probe, ctx, self._checks)

        # Log every decision (invariant #6).
        for check_name, decision in outcome.decisions:
            self._risk_logger.log_decision(
                check_name=check_name,
                decision="allow" if decision.allowed else "block",
                reason=decision.reason,
                client_order_id=str(getattr(cmd, "client_order_id", "")),
                instrument_id=probe.instrument_id,
                qty=probe.quantity,
                side=probe.side,
            )

        if not outcome.allowed:
            self._msgbus.publish(
                topic=ORDER_DENIED_TOPIC,
                msg={
                    "client_order_id": str(getattr(cmd, "client_order_id", "")),
                    "reason": outcome.reason or "gate_internal_error",
                    "blocking_check": outcome.blocking_check,
                },
            )
