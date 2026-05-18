from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from alpha_engine.reporting.metrics import (
    avg_holding_seconds,
    max_drawdown,
    sharpe,
    total_pnl,
    win_rate,
)


@dataclass(frozen=True)
class RunMetadata:
    run_id: str
    env_name: str
    mode: str
    strategy_class: str
    start_ts: datetime
    end_ts: datetime
    git_sha: str | None
    halt_cause: str | None


def write_summary(
    path: Path,
    *,
    meta: RunMetadata,
    trades: pd.DataFrame,
    pnl_daily: pd.DataFrame,
) -> None:
    payload = {
        "run_id": meta.run_id,
        "env_name": meta.env_name,
        "mode": meta.mode,
        "strategy_class": meta.strategy_class,
        "start_ts": meta.start_ts.isoformat(),
        "end_ts": meta.end_ts.isoformat(),
        "git_sha": meta.git_sha,
        "halt_cause": meta.halt_cause,
        "metrics": {
            "total_pnl": total_pnl(pnl_daily),
            "sharpe": sharpe(pnl_daily),
            "max_drawdown": max_drawdown(pnl_daily),
            "trades": len(trades),
            "win_rate": win_rate(trades),
            "avg_holding_sec": avg_holding_seconds(trades),
        },
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
