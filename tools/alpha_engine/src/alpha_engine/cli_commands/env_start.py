from __future__ import annotations

import json
from pathlib import Path

from alpha_engine.config.loader import load_env_config, ConfigError
from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.mode import Mode
from alpha_engine.engine.boot import run_backtest
from alpha_engine.strategies import default_registry  # noqa: F401  (triggers registration)


def run(*, envs_root: Path, name: str) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    if not paths.config_path.exists():
        print(f"error: env {name!r} has no config at {paths.config_path}", flush=True)
        return 1
    try:
        cfg = load_env_config(paths.config_path)
    except ConfigError as exc:
        print(f"config error: {exc}", flush=True)
        return 1

    if cfg.mode is not Mode.BACKTEST:
        print(
            f"error: Phase 1 supports only backtest mode; got mode={cfg.mode.value}. "
            "Paper/live land in Phase 2.",
            flush=True,
        )
        return 2

    if cfg.data.historical_source == "synthetic_fixture":
        from tests.fixtures.catalog_builder import build_engine_with_synthetic_bars

        def loader(_cfg, _paths):
            return build_engine_with_synthetic_bars()

    else:
        print(
            f"error: historical_source={cfg.data.historical_source!r} not registered yet. "
            "Phase 1 ships 'synthetic_fixture' only; real data sources come in Phase 1.5+.",
            flush=True,
        )
        return 3

    result = run_backtest(cfg=cfg, paths=paths, data_loader=loader)
    print(f"run_id={result.run_id}", flush=True)
    print(f"summary={result.summary_path}", flush=True)
    print(f"trades={result.trades_path}", flush=True)

    paths.last_run_path.parent.mkdir(parents=True, exist_ok=True)
    paths.last_run_path.write_text(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": "halted" if result.halt_cause else "completed",
                "halt_cause": result.halt_cause,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if result.halt_cause is None else 4
