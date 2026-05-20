"""Run the bband_v1 backtest end-to-end.

Usage:
    cd /mnt/HDD/Projects/Financial_App/tools/alpha_engine
    .venv/bin/python envs/bband_v1/run_backtest.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALPHA_ENGINE_ROOT = HERE.parent.parent  # tools/alpha_engine

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ALPHA_ENGINE_ROOT / "src"))

import config as cfg  # noqa: E402
from nautilus_trader.backtest.node import BacktestNode  # noqa: E402

from alpha_engine.logging_.bus_subscriber import (  # noqa: E402
    OrderFillRecorder,
    attach_order_fill_recorder,
)
from alpha_engine.reporting.summary import RunMetadata, write_summary  # noqa: E402
from alpha_engine.reporting.trades import write_trades_parquet  # noqa: E402


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(ALPHA_ENGINE_ROOT),
        )
        return out.strip()
    except Exception:
        return None


def main() -> int:
    cfg.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    run_config = cfg.backtest_run_config()
    node = BacktestNode(configs=[run_config])
    node.build()

    recorder = OrderFillRecorder(
        env_name="bband_v1",
        strategy_class="BBandVolumeSetupStrategy",
    )
    get_engines = getattr(node, "get_engines", None)
    if callable(get_engines):
        for engine in get_engines():
            attach_order_fill_recorder(engine.kernel.msgbus, recorder=recorder)
    else:
        # Nautilus 1.226 doesn't expose engine handles externally — fall back
        # to an empty fills list; trades.parquet will be written empty.
        recorder.records = []

    start_ts = cfg.run_started_now()
    results = node.run()
    end_ts = cfg.run_started_now()

    if not results:
        print("backtest produced no results", file=sys.stderr)
        return 1

    result = results[0]
    meta = RunMetadata(
        trader_id=result.trader_id,
        instance_id=result.instance_id,
        git_sha=_git_sha(),
        env_name="bband_v1",
        start_ts=start_ts,
        end_ts=end_ts,
    )

    write_summary(
        cfg.SUMMARY_PATH,
        meta=meta,
        stats_pnls=result.stats_pnls or {},
        stats_returns=result.stats_returns or {},
    )
    write_trades_parquet(cfg.TRADES_PARQUET_PATH, recorder.records)

    print(f"summary: {cfg.SUMMARY_PATH}")
    print(f"trades:  {cfg.TRADES_PARQUET_PATH}")
    print(f"fills:   {len(recorder.records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
