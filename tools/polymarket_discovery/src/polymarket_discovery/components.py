from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import MarketDescriptor
from .pipeline import PipelineComponents
from .providers import DeepSeekLLMProviderStub
from .stages import (
    DefaultBasketBuilder,
    DefaultBasketValidator,
    DefaultTopicAssigner,
    LLMDependencyInferencer,
    TopicEndDateCandidateReducer,
)


@dataclass(slots=True)
class FixtureMarketSource:
    """Fixture-backed market source used by the Phase 1 skeleton."""

    def fetch_active_markets(self, config: Any | None = None) -> list[MarketDescriptor]:
        params = getattr(config, "params", {}) if config is not None else {}
        raw_markets = params.get("markets")
        if isinstance(raw_markets, list) and raw_markets:
            return [MarketDescriptor(**item) for item in raw_markets]

        # Default sample is deterministic and suitable for smoke execution.
        return [
            MarketDescriptor(
                market_id="mkt-a",
                condition_id="cond-a",
                question="Will Candidate A win the election?",
                description="Election winner market",
                rules="Resolves to official election result",
                end_date="2026-11-03T23:59:59Z",
                topic="politics",
                token_ids=["tok-a-yes"],
            ),
            MarketDescriptor(
                market_id="mkt-b",
                condition_id="cond-b",
                question="Will Candidate B win the election?",
                description="Election winner market",
                rules="Resolves to official election result",
                end_date="2026-11-03",
                topic="politics",
                token_ids=["tok-b-yes"],
            ),
        ]


def build_components() -> PipelineComponents:
    return PipelineComponents(
        market_source=FixtureMarketSource(),
        topic_assigner=DefaultTopicAssigner(),
        candidate_reducer=TopicEndDateCandidateReducer(),
        dependency_inferencer=LLMDependencyInferencer(DeepSeekLLMProviderStub()),
        basket_builder=DefaultBasketBuilder(),
        basket_validator=DefaultBasketValidator(),
    )
