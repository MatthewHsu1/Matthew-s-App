"""Paper-mode engine boot — slated for deletion in PR 3."""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Importing these packages triggers @venue_adapter / @data_source registration.
import alpha_engine.adapters
import alpha_engine.data.sources  # noqa: F401
from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import EnvConfig
from alpha_engine.contracts.mode import Mode


@dataclass(frozen=True)
class PaperRunResult:
    run_id: str
    summary_path: Path
    halt_cause: str | None


def build_ibkr_client_configs(cfg: EnvConfig):
    """Resolve creds and build IBKR data + exec client configs from the env config."""
    from alpha_engine.adapters.registry import default_registry as venue_registry

    factory_cls = venue_registry.get(cfg.venue.id)
    factory = factory_cls()
    data_cfg = factory.data_client_config(cfg.venue, cfg.mode)
    exec_cfg = factory.exec_client_config(cfg.venue, cfg.mode)

    return data_cfg, exec_cfg


def run_paper(
    *,
    cfg: EnvConfig,
    paths: EnvPaths,
    trading_node_factory: Callable | None = None,
) -> PaperRunResult:
    """Boot a paper-mode env."""
    from alpha_engine.config.run_id import generate_run_id
    from alpha_engine.config.secrets import load_secrets_file
    from alpha_engine.control.boot_guards import assert_safe_to_boot
    from alpha_engine.control.last_run import LastRunWriter

    if cfg.mode is not Mode.PAPER:
        raise ValueError(f"run_paper called with mode={cfg.mode}")

    paths.ensure_dirs()

    assert_safe_to_boot(
        killfile_path=paths.kill_switch_path,
        last_run_path=paths.last_run_path,
    )

    load_secrets_file(paths.secrets_path)

    run_id = generate_run_id(env_name=cfg.env_name, config_payload={
        "strategy_ref": cfg.strategy.ref,
        "strategy_params": cfg.strategy.params,
        "instruments": list(cfg.data.instruments),
    })

    LastRunWriter(paths.last_run_path).write(
        pid=os.getpid(),
        started_ts=datetime.now(tz=timezone.utc),
        mode="paper",
        run_id=run_id,
        env_name=cfg.env_name,
    )

    data_cfg, exec_cfg = build_ibkr_client_configs(cfg)

    if trading_node_factory is None:
        from nautilus_trader.live.config import TradingNodeConfig
        from nautilus_trader.live.node import TradingNode

        _node = TradingNode(
            config=TradingNodeConfig(
                data_clients={"IBKR": data_cfg},
                exec_clients={"IBKR": exec_cfg},
            )
        )
    else:
        _node = trading_node_factory(data_cfg, exec_cfg)

    summary_path = paths.reports_dir / f"summary_{run_id}.json"
    return PaperRunResult(run_id=run_id, summary_path=summary_path, halt_cause=None)
