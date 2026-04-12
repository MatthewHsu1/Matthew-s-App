from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.cli import run_command
from polymarket_discovery.config import load_config


def test_cli_smoke_run_command_writes_output_artifacts(tmp_path: Path) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_config.json"
    config = json.loads(fixture_path.read_text(encoding="utf-8"))
    config["output_root"] = str(tmp_path / "artifacts")

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = run_command(config_path)
    assert exit_code == 0

    run_root = Path(config["output_root"]) / config["artifact_subdir"]
    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    assert len(run_dirs) == 1

    baskets_path = run_dirs[0] / "baskets.json"
    stages_path = run_dirs[0] / "stages.jsonl"
    assert baskets_path.exists()
    assert stages_path.exists()

    payload = json.loads(baskets_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "v1"
    assert payload["run_metadata"]["run_id"].startswith("run_")
    assert len(payload["dependencies"]) == 1
    assert len(payload["baskets"]) == 1
    assert payload["baskets"][0]["basket_id"].startswith("basket-")


def test_cli_respects_configured_stages(tmp_path: Path) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_config.json"
    config = json.loads(fixture_path.read_text(encoding="utf-8"))
    config["output_root"] = str(tmp_path / "artifacts")
    config["stages"] = [
        "market_source",
        "topic_assigner",
        "candidate_reducer",
    ]

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    exit_code = run_command(config_path)
    assert exit_code == 0

    run_root = Path(config["output_root"]) / config["artifact_subdir"]
    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    assert len(run_dirs) == 1

    payload = json.loads((run_dirs[0] / "baskets.json").read_text(encoding="utf-8"))
    assert payload["dependencies"] == []
    assert payload["baskets"] == []

    stage_records = [
        json.loads(line)
        for line in (run_dirs[0] / "stages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    started_stages = [r["stage"] for r in stage_records if r.get("event") == "stage_started"]
    assert started_stages == config["stages"]


def test_load_config_rejects_unknown_stage(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "artifacts"),
                "stages": ["market_source", "unknown_stage"],
            },
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown stage"):
        load_config(config_path)
