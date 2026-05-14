from __future__ import annotations

import json
from pathlib import Path

from alpha_engine.config.paths import EnvPaths


def run(*, envs_root: Path, name: str, run: str | None) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    if not paths.reports_dir.exists():
        print(f"error: no reports for env {name!r} (expected at {paths.reports_dir})", flush=True)
        return 1

    summaries = sorted(paths.reports_dir.glob("summary_*.json"))
    if not summaries:
        print(f"error: env {name!r} has no run summaries yet.", flush=True)
        return 1

    if run is None:
        path = summaries[-1]
    else:
        path = paths.reports_dir / f"summary_{run}.json"
        if not path.exists():
            print(f"error: no summary for run={run!r}", flush=True)
            return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    m = data["metrics"]
    print(f"run_id:      {data['run_id']}")
    print(f"env:         {data['env_name']}  mode={data['mode']}  strategy={data['strategy_class']}")
    print(f"period:      {data['start_ts']} → {data['end_ts']}")
    print(f"halt_cause:  {data['halt_cause']}")
    print(f"git_sha:     {data['git_sha']}")
    print("metrics:")
    print(f"  total_pnl:        {m['total_pnl']:.2f}")
    print(f"  sharpe:           {m['sharpe']:.3f}")
    print(f"  max_drawdown:     {m['max_drawdown']:.2f}")
    print(f"  trades:           {m['trades']}")
    print(f"  win_rate:         {m['win_rate']:.3f}")
    print(f"  avg_holding_sec:  {m['avg_holding_sec']:.1f}")
    return 0
