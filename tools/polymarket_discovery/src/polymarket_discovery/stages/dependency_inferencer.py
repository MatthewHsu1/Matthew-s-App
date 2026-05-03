from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from ..contracts import DependencyEdge, MarketDescriptor
from ..interfaces.dependency_inferencer import DependencyInferencer
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_provider import LLMProvider
from ..interfaces.market_pair import MarketPair
from ..providers.factories import build_llm_provider
from ..providers.factories import configures_llm_provider
from ..providers.llm_codec import DEFAULT_DEPENDENCY_BATCH_SIZE, validate_llm_dependency_prediction

if TYPE_CHECKING:
    from ..utils.logging_utils import JsonlStageLogger


class LLMDependencyInferencer(DependencyInferencer):
    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        stage_logger: JsonlStageLogger | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._stage_logger = stage_logger

    def infer_dependencies(
        self,
        market_pairs: Sequence[MarketPair],
        config: Any | None = None,
    ) -> list[DependencyEdge]:
        provider = self._resolve_provider(config)
        batch_size = self._resolve_batch_size(config)

        pairs = list(market_pairs)
        if not pairs:
            return []

        # Chunk pairs into batches; each chunk is ONE LLM call rather than N.
        predictions = []
        for chunk_start in range(0, len(pairs), batch_size):
            chunk = pairs[chunk_start : chunk_start + batch_size]
            chunk_predictions = provider.infer_dependencies_batched(chunk)
            predictions.extend(chunk_predictions)

        edges: list[DependencyEdge] = []
        for (left, right), prediction in zip(pairs, predictions):
            validated = validate_llm_dependency_prediction(prediction)
            edges.append(
                DependencyEdge(
                    edge_id=f"{left.market_id}__{right.market_id}",
                    edge_type=validated.edge_type,
                    from_market_id=left.market_id,
                    to_market_id=right.market_id,
                    confidence=validated.confidence,
                    rationale=validated.rationale,
                ),
            )

        return edges

    @staticmethod
    def _resolve_batch_size(config: Any | None) -> int:
        """Read batch_size from config.params['dependency_inferencer']['batch_size'].

        Falls back to :data:`DEFAULT_DEPENDENCY_BATCH_SIZE` (50) when not set.
        """
        try:
            params = getattr(config, "params", {}) or {}
            inferencer_params = params.get("dependency_inferencer", {})
            if isinstance(inferencer_params, dict):
                raw = inferencer_params.get("batch_size")
                if isinstance(raw, int) and raw > 0:
                    return raw
        except Exception:
            pass
        return DEFAULT_DEPENDENCY_BATCH_SIZE

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
        return build_llm_provider(config, stage_logger=self._stage_logger)
