# Polymarket Discovery (Phase 1 Skeleton)

Offline pipeline skeleton for discovering candidate arbitrage baskets before live Nautilus execution.

## Run

```bash
cd tools/polymarket_discovery
PYTHONPATH=src python3 -m polymarket_discovery run --config tests/fixtures/sample_config.json
```

Artifacts are written under `output_root/artifact_subdir/run_<hash>/`:
- `baskets.json` (schema-validated output contract)
- `stages.jsonl` (structured stage logs)

## Test Setup

```bash
cd tools/polymarket_discovery
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```
