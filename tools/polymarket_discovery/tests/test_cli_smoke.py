# ruff: noqa: E402
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
from polymarket_discovery.contracts import BasketItem, DependencyEdge, MarketDescriptor
from polymarket_discovery.pipeline import PipelineComponents


def _market(market_id: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Question {market_id}",
        description="Description",
        end_date="2026-11-03",
        topic="topic",
        token_ids=[f"tok-{market_id}-yes"],
    )


class _StaticMarketSource:
    def fetch_active_markets(self, config: object | None = None) -> list[MarketDescriptor]:
        return [_market("m1"), _market("m2")]


class _PassthroughTopicAssigner:
    def assign_topics(
        self,
        markets: list[MarketDescriptor],
        config: object | None = None,
    ) -> list[MarketDescriptor]:
        return list(markets)


class _StaticCandidateReducer:
    def reduce(
        self,
        markets: list[MarketDescriptor],
        config: object | None = None,
    ) -> list[tuple[MarketDescriptor, MarketDescriptor]]:
        return [(markets[0], markets[1])]


class _StaticDependencyInferencer:
    def infer_dependencies(
        self,
        market_pairs: list[tuple[MarketDescriptor, MarketDescriptor]],
        config: object | None = None,
    ) -> list[DependencyEdge]:
        left, right = market_pairs[0]
        return [
            DependencyEdge(
                edge_id=f"{left.market_id}__{right.market_id}",
                edge_type="mutually_exclusive",
                from_market_id=left.market_id,
                to_market_id=right.market_id,
                confidence=0.95,
                rationale="fixture rationale",
            ),
        ]


class _InvalidBasketBuilder:
    def build(
        self,
        markets: list[MarketDescriptor],
        dependencies: list[DependencyEdge],
        config: object | None = None,
        basket_groups: object = (),
    ) -> tuple[list[BasketItem], list[DependencyEdge]]:
        return (
            [
                BasketItem(
                    basket_id="basket-m1__m2",
                    token_ids=["tok-m1-yes", "tok-m2-yes"],
                    dependency_basis=["missing-edge"],
                ),
            ],
            [],
        )


class _NoopBasketValidator:
    def validate(self, baskets: list[BasketItem], config: object | None = None) -> None:
        return None


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
    import re
    assert re.fullmatch(r"run_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}", payload["run_metadata"]["run_id"]), (
        f"run_id does not match expected format: {payload['run_metadata']['run_id']!r}"
    )
    # Pairwise edge from the stub inferencer + synthetic basket-member chain edge.
    assert len(payload["dependencies"]) >= 1
    assert len(payload["baskets"]) == 1


def test_cli_default_components_use_configured_llm_model_in_stub_rationale(tmp_path: Path) -> None:
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

    payload = json.loads((run_dirs[0] / "baskets.json").read_text(encoding="utf-8"))
    assert payload["run_metadata"]["llm_model"] == config["llm_model"]
    # At least one dependency edge should carry the stub model name in its rationale.
    llm_model = config["llm_model"]
    assert any(
        edge["rationale"].startswith(f"{llm_model}:")
        for edge in payload["dependencies"]
    )


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


def test_cli_logs_run_failed_and_skips_output_write_when_final_validation_fails(
    tmp_path: Path,
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_config.json"
    config = json.loads(fixture_path.read_text(encoding="utf-8"))
    config["output_root"] = str(tmp_path / "artifacts")

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    components = PipelineComponents(
        market_source=_StaticMarketSource(),
        topic_assigner=_PassthroughTopicAssigner(),
        candidate_reducer=_StaticCandidateReducer(),
        dependency_inferencer=_StaticDependencyInferencer(),
        basket_builder=_InvalidBasketBuilder(),
        basket_validator=_NoopBasketValidator(),
    )

    with pytest.raises(ValueError, match="missing dependency edge ID"):
        run_command(config_path, components=components)

    run_root = Path(config["output_root"]) / config["artifact_subdir"]
    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    assert len(run_dirs) == 1
    artifact_dir = run_dirs[0]

    assert not (artifact_dir / "baskets.json").exists()

    stage_records = [
        json.loads(line)
        for line in (artifact_dir / "stages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert stage_records[-1]["event"] == "run_failed"
    assert stage_records[-1]["error_type"] == "OutputValidationError"
    assert "missing dependency edge ID" in stage_records[-1]["error"]


def test_cli_logs_run_failed_when_component_construction_is_misconfigured(
    tmp_path: Path,
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "sample_config.json"
    config = json.loads(fixture_path.read_text(encoding="utf-8"))
    config["output_root"] = str(tmp_path / "artifacts")
    config["market_source"] = "unsupported-source"

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported market source"):
        run_command(config_path)

    run_root = Path(config["output_root"]) / config["artifact_subdir"]
    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    assert len(run_dirs) == 1
    artifact_dir = run_dirs[0]

    assert not (artifact_dir / "baskets.json").exists()

    stage_records = [
        json.loads(line)
        for line in (artifact_dir / "stages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert stage_records[-1]["event"] == "run_failed"
    assert stage_records[-1]["error_type"] == "ValueError"
    assert "Unsupported market source" in stage_records[-1]["error"]


# ---------------------------------------------------------------------------
# generate_run_id provenance tests
# ---------------------------------------------------------------------------

def test_generate_run_id_consecutive_runs_with_same_config_produce_different_ids(
    tmp_path: Path,
) -> None:
    """Two consecutive calls to generate_run_id with identical config must yield
    distinct IDs so that Phase 2 can distinguish artifact runs from each other."""
    import time

    from polymarket_discovery.config import DiscoveryConfig, generate_run_id

    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        embedding_provider="stub",
    )

    id1 = generate_run_id(config)
    # Sleep just long enough to guarantee the second-resolution timestamp advances.
    time.sleep(1.05)
    id2 = generate_run_id(config)

    assert id1 != id2, (
        f"Expected distinct run_ids for consecutive runs with identical config, "
        f"got identical: {id1!r}"
    )


def test_generate_run_id_format_is_parseable_and_sortable(tmp_path: Path) -> None:
    """run_id must match ``run_<YYYYMMDDTHHMMSSz>_<12-hex>`` and be
    lexicographically sortable (later runs sort after earlier ones)."""
    import re
    import time

    from polymarket_discovery.config import DiscoveryConfig, generate_run_id

    _RUN_ID_RE = re.compile(r"^run_([0-9]{8}T[0-9]{6}Z)_([0-9a-f]{12})$")

    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        embedding_provider="stub",
    )

    id1 = generate_run_id(config)
    time.sleep(1.05)
    id2 = generate_run_id(config)

    # Both must match the expected pattern.
    m1 = _RUN_ID_RE.fullmatch(id1)
    m2 = _RUN_ID_RE.fullmatch(id2)
    assert m1, f"id1={id1!r} does not match run_id pattern"
    assert m2, f"id2={id2!r} does not match run_id pattern"

    # The timestamp portion must be parseable as UTC.
    from datetime import datetime, timezone
    ts1 = datetime.strptime(m1.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    ts2 = datetime.strptime(m2.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    assert ts2 >= ts1, "Second run timestamp should not precede first"

    # Lexicographic sort must agree with chronological sort.
    assert id1 < id2, (
        f"run_ids must be lexicographically sortable; expected {id1!r} < {id2!r}"
    )

    # Config-hash suffix must be identical for the same config (fingerprint preserved).
    assert m1.group(2) == m2.group(2), (
        f"Config hash should be the same for identical configs: "
        f"{m1.group(2)!r} vs {m2.group(2)!r}"
    )


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
