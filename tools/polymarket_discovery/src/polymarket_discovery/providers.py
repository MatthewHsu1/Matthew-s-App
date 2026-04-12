from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from .contracts import MarketDescriptor
from .interfaces import EmbeddingProvider
from .interfaces import LLMDependencyPrediction
from .interfaces import LLMProvider


@dataclass(slots=True)
class StubEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding stub for local tests and interface plumbing."""

    dimensions: int = 8

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values = [digest[i] / 255.0 for i in range(self.dimensions)]
            vectors.append(values)
        return vectors


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
