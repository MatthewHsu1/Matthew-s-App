from __future__ import annotations

from typing import Protocol

from ..contracts import MarketDescriptor

from .llm_dependency_prediction import LLMDependencyPrediction


class LLMProvider(Protocol):
    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        """Infer dependency metadata for a pair of markets."""
