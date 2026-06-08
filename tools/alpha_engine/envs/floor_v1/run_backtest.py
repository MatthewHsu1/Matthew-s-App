#!/usr/bin/env python3
"""Run the Floor Trading backtest against the catalog configured in config.py.

Usage:
  python envs/floor_v1/run_backtest.py [--start 2026-01-05] [--end 2026-01-15] [--catalog-path /abs/path]

Outputs land in envs/floor_v1/outputs/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from envs.floor_v1.config import (
    BACKTEST_END,
    BACKTEST_START,
    CATALOG_PATH,
    LOGS_DIR,
    OUTPUTS_DIR,
    SUMMARY_PATH,
    backtest_run_config,
    run_started_now,
)
from nautilus_trader.backtest.node import BacktestNode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=BACKTEST_START)
    parser.add_argument("--end", default=BACKTEST_END)
    parser.add_argument("--catalog-path", default=CATALOG_PATH)
    args = parser.parse_args()

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    rc = backtest_run_config(
        start=args.start, end=args.end, catalog_path=args.catalog_path,
    )
    node = BacktestNode(configs=[rc])
    results = node.run()
    assert len(results) == 1
    result = results[0]

    summary = {
        "trader_id": result.trader_id,
        "instance_id": str(result.instance_id),
        "run_started_at": run_started_now().isoformat(),
        "start": args.start, "end": args.end,
        "stats_pnls": result.stats_pnls or {},
        "stats_returns": result.stats_returns or {},
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, default=str))
    print(f"backtest complete: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
