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
from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.contracts import BasketItem
from polymarket_discovery.contracts import DependencyEdge
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.utils.logging_utils import JsonlStageLogger
from polymarket_discovery.pipeline import PipelineComponents
from polymarket_discovery.pipeline import run_pipeline
from polymarket_discovery.serialization import validate_output_document


def _load_json_fixture(name: str) -> dict[str, object]:
    path = ROOT / "tests" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _write_config(tmp_path: Path, payload: dict[str, object]) -> Path:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _read_stage_records(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_artifact_dir(config: dict[str, object]) -> Path:
    return Path(config["output_root"]) / str(config["artifact_subdir"])


def test_run_command_fixture_pipeline_produces_valid_artifact_and_full_stage_sequence(
    tmp_path: Path,
) -> None:
    config = _load_json_fixture("sample_config.json")
    config["output_root"] = str(tmp_path / "artifacts")

    exit_code = run_command(_write_config(tmp_path, config))

    assert exit_code == 0

    run_root = _run_artifact_dir(config)
    run_dirs = sorted(path for path in run_root.iterdir() if path.is_dir())
    assert len(run_dirs) == 1

    artifact_dir = run_dirs[0]
    payload = json.loads((artifact_dir / "baskets.json").read_text(encoding="utf-8"))
    validate_output_document(payload)

    assert payload["schema_version"] == "v1"
    assert payload["run_metadata"]["market_source"] == "fixture"
    assert [market["topic"] for market in payload["markets"]] == ["topic-01", "topic-01"]
    # The stub provider emits both pairwise edges (mutually_exclusive) and a basket
    # group (basket_member synthetic edge); both appear in the dependencies list.
    edge_types = {edge["edge_type"] for edge in payload["dependencies"]}
    assert "mutually_exclusive" in edge_types
    assert len(payload["baskets"]) == 1
    # Basket produced by the stub basket-group path references the synthetic chain edge.
    assert all(
        dep_id.startswith("basket-member__")
        for dep_id in payload["baskets"][0]["dependency_basis"]
    )

    stage_records = _read_stage_records(artifact_dir / "stages.jsonl")
    assert [(record["event"], record.get("stage")) for record in stage_records] == [
        ("run_started", None),
        ("stage_started", "market_source"),
        ("stage_completed", "market_source"),
        ("stage_started", "topic_assigner"),
        ("stage_completed", "topic_assigner"),
        ("stage_started", "candidate_reducer"),
        ("stage_completed", "candidate_reducer"),
        ("stage_started", "dependency_inferencer"),
        ("stage_completed", "dependency_inferencer"),
        ("stage_started", "basket_builder"),
        ("stage_completed", "basket_builder"),
        ("stage_started", "basket_validator"),
        ("stage_completed", "basket_validator"),
        ("run_completed", None),
    ]


@pytest.mark.parametrize(
    ("enabled_stages", "expected_sequence", "expected_skipped"),
    [
        (
            ["market_source"],
            [
                ("run_started", None),
                ("stage_started", "market_source"),
                ("stage_completed", "market_source"),
                ("stage_skipped", "topic_assigner"),
                ("stage_skipped", "candidate_reducer"),
                ("stage_skipped", "dependency_inferencer"),
                ("stage_skipped", "basket_builder"),
                ("stage_skipped", "basket_validator"),
                ("run_completed", None),
            ],
            [
                "topic_assigner",
                "candidate_reducer",
                "dependency_inferencer",
                "basket_builder",
                "basket_validator",
            ],
        ),
        (
            ["market_source", "topic_assigner", "candidate_reducer"],
            [
                ("run_started", None),
                ("stage_started", "market_source"),
                ("stage_completed", "market_source"),
                ("stage_started", "topic_assigner"),
                ("stage_completed", "topic_assigner"),
                ("stage_started", "candidate_reducer"),
                ("stage_completed", "candidate_reducer"),
                ("stage_skipped", "dependency_inferencer"),
                ("stage_skipped", "basket_builder"),
                ("stage_skipped", "basket_validator"),
                ("run_completed", None),
            ],
            [
                "dependency_inferencer",
                "basket_builder",
                "basket_validator",
            ],
        ),
    ],
)
def test_run_command_logs_stage_skips_in_artifact_sequence(
    tmp_path: Path,
    enabled_stages: list[str],
    expected_sequence: list[tuple[str, str | None]],
    expected_skipped: list[str],
) -> None:
    config = _load_json_fixture("sample_config.json")
    config["output_root"] = str(tmp_path / "artifacts")
    config["stages"] = enabled_stages

    exit_code = run_command(_write_config(tmp_path, config))

    assert exit_code == 0

    run_root = _run_artifact_dir(config)
    run_dirs = sorted(path for path in run_root.iterdir() if path.is_dir())
    assert len(run_dirs) == 1

    artifact_dir = run_dirs[0]
    payload = json.loads((artifact_dir / "baskets.json").read_text(encoding="utf-8"))
    validate_output_document(payload)

    assert payload["dependencies"] == []
    assert payload["baskets"] == []

    stage_records = _read_stage_records(artifact_dir / "stages.jsonl")
    assert [(record["event"], record.get("stage")) for record in stage_records] == expected_sequence
    assert [record["stage"] for record in stage_records if record["event"] == "stage_skipped"] == expected_skipped
    assert all(record["reason"] == "disabled_in_config" for record in stage_records if record["event"] == "stage_skipped")


def _market(
    market_id: str,
    *,
    topic: str = "topic-01",
    end_date: str = "2026-11-03",
) -> MarketDescriptor:
    # Binary market with YES and NO tokens; exercises the completeness rule
    # (basket token_ids must equal the union of all participating market token_ids).
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Question {market_id}",
        description="Description",
        rules="Rules",
        end_date=end_date,
        topic=topic,
        token_ids=[f"tok-{market_id}-yes", f"tok-{market_id}-no"],
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


def test_run_pipeline_rejects_invalid_basket_at_final_schema_gate(tmp_path: Path) -> None:
    config = DiscoveryConfig(output_root=tmp_path / "artifacts", embedding_provider="stub")
    stage_logger = JsonlStageLogger(path=tmp_path / "stages.jsonl", run_id="run-test")
    components = PipelineComponents(
        market_source=_StaticMarketSource(),
        topic_assigner=_PassthroughTopicAssigner(),
        candidate_reducer=_StaticCandidateReducer(),
        dependency_inferencer=_StaticDependencyInferencer(),
        basket_builder=_InvalidBasketBuilder(),
        basket_validator=_NoopBasketValidator(),
    )

    with pytest.raises(ValueError, match="missing dependency edge ID"):
        run_pipeline(config=config, components=components, stage_logger=stage_logger)

    stage_records = _read_stage_records(stage_logger.path)
    assert [(record["event"], record.get("stage")) for record in stage_records] == [
        ("stage_started", "market_source"),
        ("stage_completed", "market_source"),
        ("stage_started", "topic_assigner"),
        ("stage_completed", "topic_assigner"),
        ("stage_started", "candidate_reducer"),
        ("stage_completed", "candidate_reducer"),
        ("stage_started", "dependency_inferencer"),
        ("stage_completed", "dependency_inferencer"),
        ("stage_started", "basket_builder"),
        ("stage_completed", "basket_builder"),
        ("stage_started", "basket_validator"),
        ("stage_completed", "basket_validator"),
    ]
