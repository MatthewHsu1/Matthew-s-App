from __future__ import annotations

import json
from pathlib import Path

from alpha_engine.config.loader import load_env_config, ConfigError
from alpha_engine.config.paths import EnvPaths
from alpha_engine.contracts.mode import Mode
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

    from alpha_engine.engine.boot import dispatch_mode

    fn = dispatch_mode(cfg)

    if cfg.mode is Mode.BACKTEST:
        # Backtest still uses the synthetic fixture loader pattern from Phase 1.
        if cfg.data.historical_source != "synthetic_fixture":
            print(
                f"error: backtest with historical_source={cfg.data.historical_source!r} "
                "not yet wired through the cache. Use synthetic_fixture for now or "
                "wait for the data-source registry integration.",
                flush=True,
            )
            return 3
        from alpha_engine.data.sources.synthetic_fixture import build_engine_with_synthetic_bars

        def loader(_cfg, _paths):
            return build_engine_with_synthetic_bars()

        result = fn(cfg=cfg, paths=paths, data_loader=loader)
        print(f"run_id={result.run_id}", flush=True)
        print(f"summary={result.summary_path}", flush=True)
        print(f"trades={result.trades_path}", flush=True)

        # Backtest path: write last_run.json here (paper writes its own internally).
        paths.last_run_path.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        paths.last_run_path.write_text(
            _json.dumps(
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

    # Paper mode.
    result = fn(cfg=cfg, paths=paths)
    print(f"run_id={result.run_id}", flush=True)
    print(f"summary={result.summary_path}", flush=True)
    return 0
