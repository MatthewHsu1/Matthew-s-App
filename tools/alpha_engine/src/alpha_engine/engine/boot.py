from __future__ import annotations

from alpha_engine.contracts.config import EnvConfig
from alpha_engine.contracts.mode import Mode


def dispatch_mode(cfg: EnvConfig):
    """Return the boot function for the given mode."""
    if cfg.mode is Mode.BACKTEST:
        from alpha_engine.engine.backtest import run_backtest
        return run_backtest
    
    if cfg.mode is Mode.PAPER:
        from alpha_engine.engine.paper import run_paper
        return run_paper
    
    if cfg.mode is Mode.LIVE:
        raise NotImplementedError(
            f"mode=live is Phase 3, not Phase 2. env={cfg.env_name}"
        )
    
    raise ValueError(f"unknown mode {cfg.mode!r}")
