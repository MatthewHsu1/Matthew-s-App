from __future__ import annotations

from pathlib import Path

from alpha_engine.control.kill_switch_file import (
    is_kill_switch_set,
    touch_kill_switch,
    clear_kill_switch,
)
from alpha_engine.risk.check import OrderProbe, RiskContext
from alpha_engine.risk.kill_switch import make_kill_switch_check


def _probe():
    return OrderProbe(instrument_id="MSFT.NASDAQ", side="BUY", quantity=1, limit_price=100.0)


def test_kill_switch_file_lifecycle(tmp_path: Path):
    kill = tmp_path / ".KILL"
    assert not is_kill_switch_set([kill])
    touch_kill_switch(kill)
    assert kill.exists()
    assert is_kill_switch_set([kill])
    clear_kill_switch(kill)
    assert not kill.exists()
    assert not is_kill_switch_set([kill])


def test_check_blocks_when_any_kill_file_present(tmp_path: Path):
    global_kill = tmp_path / "global" / ".KILL"
    env_kill = tmp_path / "env" / ".KILL"
    env_kill.parent.mkdir(parents=True)
    global_kill.parent.mkdir(parents=True)

    check = make_kill_switch_check(paths=[global_kill, env_kill])
    ctx = RiskContext()

    assert check(_probe(), ctx).allowed

    env_kill.write_text("")
    d = check(_probe(), ctx)
    assert not d.allowed
    assert "kill_switch" in d.reason
