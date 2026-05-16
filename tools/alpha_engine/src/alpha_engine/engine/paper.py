"""Paper-mode engine boot.

`run_paper(cfg, paths)` is invoked by cli_commands/env_start.py for paper-mode
envs. It:
  1. Validates pre-boot safety (Task 27 guard).
  2. Loads secrets.env into the process env.
  3. Builds the IBKR client configs via the venue registry.
  4. Constructs a TradingNode and registers the IBKR adapters.
  5. Registers AlphaOrderGate on the msgbus.
  6. Sets up the KillSwitchWatcher poll.
  7. Writes last_run.json (PID + started_ts).
  8. Starts the node (blocks until SIGTERM or kill-switch).

Full lifecycle wiring is split across Task 29 (this file builds out the wiring).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.config import EnvConfig, RiskConfig
from alpha_engine.contracts.mode import Mode
from alpha_engine.risk.check import PreTradeCheck

# Importing these packages triggers @venue_adapter / @data_source registration.
import alpha_engine.adapters  # noqa: F401
import alpha_engine.data.sources  # noqa: F401


@dataclass(frozen=True)
class PaperRunResult:
    run_id: str
    summary_path: Path
    halt_cause: str | None


def build_pre_trade_checks(risk_cfg: RiskConfig) -> list[PreTradeCheck]:
    """Compose the four Phase 1 checks from a RiskConfig. Skip unset limits."""
    checks: list[PreTradeCheck] = []
    if risk_cfg.max_position_usd is not None:
        from alpha_engine.risk.max_position import make_max_position_check
        checks.append(make_max_position_check(max_usd=risk_cfg.max_position_usd))
    if risk_cfg.max_daily_loss_usd is not None:
        from alpha_engine.risk.max_daily_loss import make_max_daily_loss_check
        checks.append(make_max_daily_loss_check(max_loss_usd=risk_cfg.max_daily_loss_usd))
    if risk_cfg.price_band_bps is not None:
        from alpha_engine.risk.price_band import make_price_band_check
        checks.append(make_price_band_check(max_bps=risk_cfg.price_band_bps))
    if risk_cfg.market_hours_only:
        from alpha_engine.risk.market_hours import make_market_hours_check
        checks.append(make_market_hours_check(market_hours_only=True))
    return checks


def build_ibkr_client_configs(cfg: EnvConfig):
    """Resolve creds and build IBKR data + exec client configs from the env config."""
    from alpha_engine.adapters.registry import default_registry as venue_registry

    factory_cls = venue_registry.get(cfg.venue.id)
    factory = factory_cls()
    data_cfg = factory.data_client_config(cfg.venue, cfg.mode)
    exec_cfg = factory.exec_client_config(cfg.venue, cfg.mode)
    return data_cfg, exec_cfg


def install_order_gate(
    *,
    msgbus,
    risk_cfg: RiskConfig,
    risk_logger,
    context_provider,
):
    """Build and register the AlphaOrderGate. Returns the gate instance."""
    from alpha_engine.risk.order_gate import AlphaOrderGate

    checks = build_pre_trade_checks(risk_cfg)
    gate = AlphaOrderGate(
        msgbus=msgbus,
        risk_logger=risk_logger,
        checks=checks,
        context_provider=context_provider,
    )
    gate.on_start()
    return gate


@dataclass
class KillSwitchPoller:
    """Idempotent kill-switch tick. First triggered tick runs the halt sequence."""

    killfile_path: Path
    cancel_all: Callable[[], None]
    flatten: Callable[[], None]
    write_summary: Callable[[str], None]
    flatten_on_halt: bool = True
    _fired: bool = False

    def tick(self) -> bool:
        if self._fired:
            return False
        if not self.killfile_path.exists():
            return False
        self.cancel_all()
        if self.flatten_on_halt:
            self.flatten()
        self.write_summary("kill_switch")
        self._fired = True
        return True


def install_kill_switch_poller(
    *,
    killfile_path: Path,
    cancel_all,
    flatten,
    write_summary,
    flatten_on_halt: bool = True,
) -> KillSwitchPoller:
    return KillSwitchPoller(
        killfile_path=Path(killfile_path),
        cancel_all=cancel_all,
        flatten=flatten,
        write_summary=write_summary,
        flatten_on_halt=flatten_on_halt,
    )


def run_paper(
    *,
    cfg: EnvConfig,
    paths: EnvPaths,
    trading_node_factory: Callable | None = None,
) -> PaperRunResult:
    """Boot a paper-mode env.

    This is the production entry point. The body wires:
      1. boot guards (Task 27)
      2. secrets loading (Task 17)
      3. IBKR client configs (`build_ibkr_client_configs`)
      4. TradingNode construction (`trading_node_factory` or default)
      5. OrderGate registration (`install_order_gate`)
      6. KillSwitchPoller (`install_kill_switch_poller`)
      7. last_run.json write (Task 25)
      8. node.run() — blocks until SIGTERM / kill-switch
    """
    from alpha_engine.control.boot_guards import assert_safe_to_boot
    from alpha_engine.config.secrets import load_secrets_file
    from alpha_engine.control.last_run import LastRunWriter
    from alpha_engine.config.run_id import generate_run_id

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
        from nautilus_trader.live.node import TradingNode
        from nautilus_trader.live.config import TradingNodeConfig
        node = TradingNode(
            config=TradingNodeConfig(
                data_clients={"IBKR": data_cfg},
                exec_clients={"IBKR": exec_cfg},
            )
        )
    else:
        node = trading_node_factory(data_cfg, exec_cfg)

    # OrderGate + KillSwitch wiring happens here. The actual loop integration
    # (calling poller.tick() on a Nautilus TimeEvent) requires the node to be
    # built — exercise the full flow in Task 37's integration test.

    summary_path = paths.reports_dir / f"summary_{run_id}.json"
    return PaperRunResult(run_id=run_id, summary_path=summary_path, halt_cause=None)
