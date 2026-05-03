from __future__ import annotations

from itertools import combinations
from typing import Any, Sequence

from ..contracts import DependencyEdge, MarketDescriptor
from ..interfaces.dependency_inferencer import DependencyInferencer
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_provider import LLMProvider
from ..interfaces.market_pair import MarketPair
from ..providers.factories import build_llm_provider
from ..providers.factories import configures_llm_provider
from ..providers.llm_codec import validate_llm_dependency_prediction


class LLMDependencyInferencer(DependencyInferencer):
    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider

    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        provider = self._resolve_provider(config)

        edges: list[DependencyEdge] = []

        for left, right in market_pairs:
            prediction = validate_llm_dependency_prediction(
                provider.infer_dependency(left, right)
            )

            edges.append(
                DependencyEdge(
                    edge_id=f"{left.market_id}__{right.market_id}",
                    edge_type=prediction.edge_type,
                    from_market_id=left.market_id,
                    to_market_id=right.market_id,
                    confidence=prediction.confidence,
                    rationale=prediction.rationale,
                ),
            )

        return edges

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[LLMBasketGroup]:
        """Ask the configured LLM provider to infer N-way basket groupings.

        The *markets* sequence should be a single topic group (same topic and
        end date) — typically the full set of markets returned by the topic
        assigner for one cluster.  The provider's ``infer_basket_groups``
        method is called once per topic group.

        Returns ``[]`` when the provider does not support basket inference or
        when fewer than two markets are provided.
        """
        provider = self._resolve_provider(config)
        if len(markets) < 2:
            return []
        return provider.infer_basket_groups(markets)

    def _resolve_provider(self, config: Any | None) -> LLMProvider:
        if self._llm_provider is not None and not configures_llm_provider(config):
            return self._llm_provider
        return build_llm_provider(config)
