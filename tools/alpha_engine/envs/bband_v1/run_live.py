"""Boot the bband_v1 strategy in LIVE mode via IBKR TradingNode.

DANGER: this submits real orders against the IBKR account named by
$IBKR_ACCOUNT_ID. Confirm you intend to trade live before invoking.

Usage:
    cd /mnt/HDD/Projects/Financial_App/tools/alpha_engine
    .venv/bin/python envs/bband_v1/run_live.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALPHA_ENGINE_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ALPHA_ENGINE_ROOT / "src"))

import config as cfg  # noqa: E402
from nautilus_trader.adapters.interactive_brokers.factories import (  # noqa: E402
    InteractiveBrokersLiveDataClientFactory,
    InteractiveBrokersLiveExecClientFactory,
)
from nautilus_trader.live.node import TradingNode  # noqa: E402

from alpha_engine.config.secrets import load_secrets_file  # noqa: E402


def main() -> int:
    cfg.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    load_secrets_file(cfg.SECRETS_PATH)

    node = TradingNode(config=cfg.trading_node_config(is_live=True))
    node.add_data_client_factory("IB", InteractiveBrokersLiveDataClientFactory)
    node.add_exec_client_factory("IB", InteractiveBrokersLiveExecClientFactory)
    node.build()

    try:
        node.run()
    finally:
        node.stop()
        node.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
