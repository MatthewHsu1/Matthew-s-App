from __future__ import annotations

from dataclasses import dataclass

from ..contracts import MarketDescriptor
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider


@dataclass(slots=True)
class DeepSeekLLMProviderStub(LLMProvider):
    """DeepSeek-oriented stub that returns deterministic edge predictions."""

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
