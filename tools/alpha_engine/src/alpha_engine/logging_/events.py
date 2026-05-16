from __future__ import annotations

# Event names used across engine logs. Keep this list as the canonical taxonomy.
ENGINE_STARTED = "engine_started"
ENGINE_HALTED = "engine_halted"
ORDER_SUBMITTED = "order_submitted"
ORDER_ACKED = "order_acked"
ORDER_PARTIAL_FILL = "order_partial_fill"
ORDER_FILLED = "order_filled"
ORDER_CANCELED = "order_canceled"
ORDER_REJECTED = "order_rejected"
RISK_CHECK = "risk_check"
HALT_CAUSE_KILL_SWITCH = "kill_switch"
HALT_CAUSE_DAILY_LOSS = "daily_loss"
HALT_CAUSE_STRATEGY_BUG = "strategy_bug"

# Phase 2
PRE_TRADE_CHECK = "pre_trade_check"
KILL_SWITCH_TRIGGERED = "kill_switch_triggered"
KILL_SWITCH_HALT_COMPLETE = "kill_switch_halt_complete"
VENUE_RECONNECTING = "venue_reconnecting"
