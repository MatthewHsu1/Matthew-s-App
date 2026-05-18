from __future__ import annotations

from alpha_engine.contracts.decision import Decision
from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.order_gate import gate_decision


def _probe():
    return OrderProbe(instrument_id="AAPL.NASDAQ", side="BUY", quantity=10, limit_price=100.0)


def _ctx():
    return RiskContext()


def _allow_check(name="ok"):
    def f(probe, ctx):
        return Decision.allow()
    f.name = name
    return f


def _block_check(name="nope", reason="blocked"):
    def f(probe, ctx):
        return Decision.block(reason)
    f.name = name
    return f


def _raise_check(name="boom"):
    def f(probe, ctx):
        raise RuntimeError("kaboom")
    f.name = name
    return f


def test_all_allow_returns_allowed():
    outcome = gate_decision(_probe(), _ctx(), [_allow_check("a"), _allow_check("b")])
    assert outcome.allowed
    assert outcome.blocking_check is None
    assert len(outcome.decisions) == 2
    assert all(d.allowed for _, d in outcome.decisions)


def test_first_block_short_circuits():
    outcome = gate_decision(
        _probe(),
        _ctx(),
        [_allow_check("a"), _block_check("b", "limit"), _allow_check("c")],
    )
    assert not outcome.allowed
    assert outcome.blocking_check == "b"
    assert outcome.reason == "limit"
    # Third check should NOT have run.
    assert [n for n, _ in outcome.decisions] == ["a", "b"]


def test_check_raising_fails_closed():
    outcome = gate_decision(_probe(), _ctx(), [_raise_check("boom")])
    assert not outcome.allowed
    assert outcome.blocking_check == "boom"
    assert outcome.reason == "gate_internal_error"


def test_empty_check_list_is_allow():
    outcome = gate_decision(_probe(), _ctx(), [])
    assert outcome.allowed
    assert outcome.decisions == []
