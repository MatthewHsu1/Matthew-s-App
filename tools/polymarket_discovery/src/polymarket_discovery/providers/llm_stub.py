from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..contracts import MarketDescriptor
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider


@dataclass(slots=True)
class DeepSeekLLMProviderStub(LLMProvider):
    """DeepSeek-oriented stub that returns deterministic edge predictions.

    Also implements :meth:`infer_basket_groups` by returning a single basket
    covering all markets in the group — useful for exercising the basket-
    inference path in stub-provider tests without a live LLM.
    """

    model_name: str = "deepseek-stub"

    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        left = left_market.question.lower()
        right = right_market.question.lower()
        if self._looks_mutually_exclusive(left, right):
            return LLMDependencyPrediction(
                edge_type="mutually_exclusive",
                confidence=0.95,
                rationale=f"{self.model_name}: lexical exclusivity heuristic matched",
            )

        return LLMDependencyPrediction(
            edge_type="related",
            confidence=0.6,
            rationale=f"{self.model_name}: default related classification",
        )

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Return a single basket covering all provided markets.

        This deterministic stub treats the whole topic group as one complete
        outcome set (e.g. four candidates in an election, each with a YES
        token whose prices sum to 1.0).  The basket_id is derived from the
        sorted market IDs so the result is stable across runs.
        """
        if len(markets) < 2:
            return []
        sorted_ids = sorted(m.market_id for m in markets)
        basket_id = "stub-basket-" + "-".join(sorted_ids)
        return [
            LLMBasketGroup(
                basket_id=basket_id,
                market_ids=sorted_ids,
                rationale=(
                    f"{self.model_name}: stub basket covering all "
                    f"{len(sorted_ids)} markets in the topic group"
                ),
            )
        ]

    @staticmethod
    def _looks_mutually_exclusive(left: str, right: str) -> bool:
        conflict_terms = (
            ("yes", "no"),
            ("win", "lose"),
            ("democrat", "republican"),
            ("candidate a", "candidate b"),
        )
        for a, b in conflict_terms:
            if (a in left and b in right) or (b in left and a in right):
                return True
        return False
