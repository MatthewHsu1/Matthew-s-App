from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from alpha_engine.contracts.decision import Decision
from alpha_engine.control.kill_switch_file import is_kill_switch_set
from alpha_engine.risk.check import OrderProbe, PreTradeCheck, RiskContext


def make_kill_switch_check(*, paths: Iterable[Path]) -> PreTradeCheck:
    watched = tuple(Path(p) for p in paths)

    def check(probe: OrderProbe, ctx: RiskContext) -> Decision:
        if is_kill_switch_set(watched):
            return Decision.block("kill_switch active: refusing to submit orders")
        
        return Decision.allow()

    check.name = "kill_switch"  # type: ignore[attr-defined]
    return check  # type: ignore[return-value]
