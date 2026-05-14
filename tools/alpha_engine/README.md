# Alpha Engine

NautilusTrader-based alpha execution engine. **Phase 1 = backtest mode only.**
Paper / live trading land in Phase 2 (IBKR adapter). See design spec:
`docs/superpowers/specs/2026-05-14-alpha-engine-design.md`.

## Install (dev)

Alpha Engine owns its own venv. Don't reuse a sibling project's venv — Nautilus and its transitive deps belong here.

```bash
cd tools/alpha_engine
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
source .venv/bin/activate
```

Plain `pip` works too (`python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`); `uv` is just faster.

## Quickstart — backtest a toy strategy

```bash
alpha-engine env new toy --from-template backtest
alpha-engine env start toy
alpha-engine report toy
```

Outputs land under `envs/toy/`:

- `logs/engine.jsonl` — engine lifecycle (boot, halt, errors)
- `logs/orders.jsonl` — every order event (submit, fill, cancel, reject)
- `reports/trades.parquet` — per-fill trade journal
- `reports/summary_<run_id>.json` — headline metrics (PnL, Sharpe, drawdown, win rate)

## Folder layout

```
src/alpha_engine/
  cli.py                # alpha-engine CLI entry point
  contracts/            # Mode enum, Decision, EnvConfig dataclasses
  config/               # jsonschema + loader + path/run-id helpers
  strategies/           # registry + built-in toy strategy
  risk/                 # pre-trade checks (max_position, max_daily_loss, price_band, market_hours, kill_switch)
  logging_/             # JSONL handler + Nautilus msgbus subscriber
  reporting/            # trades parquet + metrics + summary.json
  engine/               # backtest boot
  control/              # env_dirs + kill_switch_file
  cli_commands/         # one module per subcommand
envs/                   # runtime payload, gitignored
configs/templates/      # committed config templates
tests/unit/             # ~80% of the suite
tests/integration/      # end-to-end backtest test
```

## Safety

Phase 1 is backtest-only. Even so, the kill-switch is wired:

```bash
alpha-engine kill-all       # creates envs/.KILL
rm tools/alpha_engine/envs/.KILL    # recover
```

When Phase 2 lands and `mode: paper | live` is enabled, this same file halts
all running envs.

## Running tests

```bash
cd tools/alpha_engine
python -m pytest tests/unit -v
python -m pytest tests/integration -v
```

## What's next

Phase 2 adds the IBKR venue adapter and paper-trading mode.
See `docs/superpowers/plans/` for the Phase 2 plan when it's written.
