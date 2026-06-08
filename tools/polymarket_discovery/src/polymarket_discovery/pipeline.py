from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from .config import DiscoveryConfig
from .contracts import ArbitrageOutputDocument, RunMetadata
from .interfaces.basket_builder import BasketBuilder
from .interfaces.basket_validator import BasketValidator
from .interfaces.candidate_reducer import CandidateReducer
from .interfaces.dependency_inferencer import DependencyInferencer
from .interfaces.market_source import MarketSource
from .interfaces.topic_assigner import TopicAssigner
from .serialization import to_output_json, validate_output_document
from .utils.jsonl_logging import stage

logger = logging.getLogger(__name__)


def _run_stage(name: str, *, enabled: bool, default, fn):
    """Run a pipeline stage if enabled, otherwise skip it.

    When *enabled* is True the stage context manager is used so that
    stage_started and stage_completed records are emitted automatically.
    When *enabled* is False a single stage_skipped record is logged and
    *default* is returned without calling *fn*.
    """
    if enabled:
        with stage(name):
            return fn()
    logger.info("stage_skipped", extra={"stage": name, "reason": "disabled_in_config"})
    return default


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
    run_id: str,
) -> PipelineRunResult:
    enabled_stages = set(config.stages)

    def _is_enabled(stage_name: str) -> bool:
        return stage_name in enabled_stages

    if not _is_enabled("market_source"):
        raise ValueError("Stage 'market_source' is required for pipeline execution.")

    with stage("market_source"):
        markets = components.market_source.fetch_active_markets(config)

    markets_with_topics = _run_stage(
        "topic_assigner",
        enabled=_is_enabled("topic_assigner"),
        default=list(markets),
        fn=lambda: components.topic_assigner.assign_topics(markets, config),
    )

    candidates = _run_stage(
        "candidate_reducer",
        enabled=_is_enabled("candidate_reducer"),
        default=[],
        fn=lambda: components.candidate_reducer.reduce(markets_with_topics, config),
    )

    dependencies = _run_stage(
        "dependency_inferencer",
        enabled=_is_enabled("dependency_inferencer"),
        default=[],
        fn=lambda: components.dependency_inferencer.infer_dependencies(candidates, config),
    )

    # Basket-structure inference: ask the LLM provider to identify N-way
    # groupings per (topic, canonical_end_date) bucket before passing control
    # to the basket builder.  Bucketing by end date is required so the LLM
    # never sees markets that resolve at different times in the same group —
    # those cannot satisfy the convergence-to-1.00 invariant.
    from collections import defaultdict

    from .interfaces.llm_basket_group import LLMBasketGroup
    from .stages.dependency_inferencer import LLMDependencyInferencer
    from .stages.topic_assigner import canonicalize_end_date

    basket_groups: list[LLMBasketGroup] = []
    if _is_enabled("dependency_inferencer") and isinstance(
        components.dependency_inferencer, LLMDependencyInferencer
    ):
        topic_end_date_buckets: dict[tuple[str, str], list] = defaultdict(list)
        for market in markets_with_topics:
            topic_key = (market.topic or "").strip().lower()
            end_date_key = canonicalize_end_date(market.end_date)
            if topic_key and end_date_key:
                topic_end_date_buckets[(topic_key, end_date_key)].append(market)
        for topic_group in topic_end_date_buckets.values():
            if len(topic_group) >= 2:
                basket_groups.extend(
                    components.dependency_inferencer.infer_basket_groups(topic_group, config)
                )

    baskets, synthetic_edges = _run_stage(
        "basket_builder",
        enabled=_is_enabled("basket_builder"),
        default=([], []),
        fn=lambda: components.basket_builder.build(
            markets_with_topics, dependencies, config, basket_groups=basket_groups
        ),
    )

    all_dependencies = list(dependencies) + synthetic_edges

    _run_stage(
        "basket_validator",
        enabled=_is_enabled("basket_validator"),
        default=None,
        fn=lambda: components.basket_validator.validate(baskets, config),
    )

    run_metadata = RunMetadata(
        run_id=run_id,
        generated_at_utc=datetime.now(UTC).isoformat(),
        market_source=config.market_source,
        embedding_model=config.embedding_model,
        llm_model=config.llm_model,
        embedding_provider=config.embedding_provider,
    )

    document = ArbitrageOutputDocument(
        run_metadata=run_metadata,
        markets=list(markets_with_topics),
        dependencies=all_dependencies,
        baskets=list(baskets),
    )
    
    validate_output_document(document)

    return PipelineRunResult(document=document)


def write_run_artifact(result: PipelineRunResult, output_path: str) -> None:
    payload = to_output_json(result.document)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")


def build_default_components(
    config: DiscoveryConfig,
) -> PipelineComponents:
    from .components import build_components

    components = build_components(config)
    if not isinstance(components, PipelineComponents):
        raise TypeError("build_components() must return PipelineComponents.")
    return components
