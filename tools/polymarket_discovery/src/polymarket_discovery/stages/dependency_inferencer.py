from __future__ import annotations

from typing import Any, Sequence

from ..contracts import DependencyEdge
from ..interfaces.dependency_inferencer import DependencyInferencer
from ..interfaces.llm_provider import LLMProvider
from ..interfaces.market_pair import MarketPair
from ..providers.factories import build_llm_provider
from ..providers.factories import configures_llm_provider
from ..providers.llm_openai import validate_llm_dependency_prediction


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

    def _resolve_provider(self, config: Any | None) -> LLMProvider:
        if self._llm_provider is not None and not configures_llm_provider(config):
            return self._llm_provider
        return build_llm_provider(config)
