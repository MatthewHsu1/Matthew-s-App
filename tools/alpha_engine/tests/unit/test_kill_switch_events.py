from alpha_engine.logging_.events import (
    KILL_SWITCH_HALT_COMPLETE,
    KILL_SWITCH_TRIGGERED,
    PRE_TRADE_CHECK,
    VENUE_RECONNECTING,
)


def test_event_constants_are_unique_strings():
    events = {KILL_SWITCH_TRIGGERED, KILL_SWITCH_HALT_COMPLETE, PRE_TRADE_CHECK, VENUE_RECONNECTING}
    assert len(events) == 4
    for e in events:
        assert isinstance(e, str) and len(e) > 0
