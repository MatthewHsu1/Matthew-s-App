from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .config import DiscoveryConfig
from .contracts import ArbitrageOutputDocument, RunMetadata
from .interfaces import (
    BasketBuilder,
    BasketValidator,
    CandidateReducer,
    DependencyInferencer,
    MarketSource,
    TopicAssigner,
)
from .logging_utils import JsonlStageLogger
from .serialization import to_output_json, validate_output_document


@dataclass(slots=True)
class PipelineComponents:
    market_source: MarketSource
    topic_assigner: TopicAssigner
    candidate_reducer: CandidateReducer
    dependency_inferencer: DependencyInferencer
    basket_builder: BasketBuilder
    basket_validator: BasketValidator


@dataclass(slots=True)
class PipelineRunResult:
    document: ArbitrageOutputDocument


def run_pipeline(
    *,
    config: DiscoveryConfig,
    components: PipelineComponents,
    stage_logger: JsonlStageLogger,
) -> PipelineRunResult:
    enabled_stages = set(config.stages)

    def _is_enabled(stage_name: str) -> bool:
        return stage_name in enabled_stages

    if not _is_enabled("market_source"):
        raise ValueError("Stage 'market_source' is required for pipeline execution.")

    with stage_logger.stage("market_source"):
        markets = components.market_source.fetch_active_markets(config)

    if _is_enabled("topic_assigner"):
        with stage_logger.stage("topic_assigner"):
            markets_with_topics = components.topic_assigner.assign_topics(markets, config)
    else:
        stage_logger.log(event="stage_skipped", stage="topic_assigner", reason="disabled_in_config")
        markets_with_topics = list(markets)

    if _is_enabled("candidate_reducer"):
        with stage_logger.stage("candidate_reducer"):
            candidates = components.candidate_reducer.reduce(markets_with_topics, config)
    else:
        stage_logger.log(event="stage_skipped", stage="candidate_reducer", reason="disabled_in_config")
        candidates = []

    if _is_enabled("dependency_inferencer"):
        with stage_logger.stage("dependency_inferencer"):
            dependencies = components.dependency_inferencer.infer_dependencies(candidates, config)
    else:
        stage_logger.log(event="stage_skipped", stage="dependency_inferencer", reason="disabled_in_config")
        dependencies = []

    if _is_enabled("basket_builder"):
        with stage_logger.stage("basket_builder"):
            baskets = components.basket_builder.build(markets_with_topics, dependencies, config)
    else:
        stage_logger.log(event="stage_skipped", stage="basket_builder", reason="disabled_in_config")
        baskets = []

    if _is_enabled("basket_validator"):
        with stage_logger.stage("basket_validator"):
            components.basket_validator.validate(baskets, config)
    else:
        stage_logger.log(event="stage_skipped", stage="basket_validator", reason="disabled_in_config")

    run_metadata = RunMetadata(
        run_id=stage_logger.run_id,
        generated_at_utc=datetime.now(UTC).isoformat(),
        market_source=config.market_source,
        embedding_model=config.embedding_model,
        llm_model=config.llm_model,
    )
    document = ArbitrageOutputDocument(
        run_metadata=run_metadata,
        markets=list(markets_with_topics),
        dependencies=list(dependencies),
        baskets=list(baskets),
    )
    validate_output_document(document)

    return PipelineRunResult(document=document)


def write_run_artifact(result: PipelineRunResult, output_path: str) -> None:
    payload = to_output_json(result.document)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")


def build_default_components(config: DiscoveryConfig | None = None) -> PipelineComponents:
    from .components import build_components

    components = build_components(config)
    if not isinstance(components, PipelineComponents):
        raise TypeError("build_components() must return PipelineComponents.")
    return components
