"""Write a thin env-stamped summary.json from PortfolioAnalyzer outputs.

`stats_pnls` and `stats_returns` come straight from
`PortfolioAnalyzer.get_performance_stats_pnls()` /
`get_performance_stats_returns()` on the BacktestResult / live node's
portfolio. We don't compute anything here — just decorate with run
metadata (trader_id, instance_id, git_sha, env_name, timestamps) so the
report is self-describing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunMetadata:
    trader_id: str
    instance_id: str
    git_sha: str | None
    env_name: str
    start_ts: datetime
    end_ts: datetime


def write_summary(
    path: Path,
    *,
    meta: RunMetadata,
    stats_pnls: dict,
    stats_returns: dict,
) -> None:
    payload = {
        "trader_id": meta.trader_id,
        "instance_id": meta.instance_id,
        "git_sha": meta.git_sha,
        "env_name": meta.env_name,
        "start_ts": meta.start_ts.isoformat(),
        "end_ts": meta.end_ts.isoformat(),
        "metrics": {
            "pnls": stats_pnls,
            "returns": stats_returns,
        },
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
