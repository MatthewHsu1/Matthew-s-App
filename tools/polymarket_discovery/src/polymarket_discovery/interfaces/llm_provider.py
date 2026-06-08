from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..contracts import MarketDescriptor
from .llm_basket_group import LLMBasketGroup
from .llm_dependency_prediction import LLMDependencyPrediction
from .market_pair import MarketPair


class LLMProvider(Protocol):
    def infer_dependencies_batched(
        self,
        pairs: Sequence[MarketPair],
    ) -> list[LLMDependencyPrediction]:
        """Infer dependency metadata for a batch of market pairs in a single call.

        ``pairs`` is a sequence of ``(left_market, right_market)`` tuples.
        Returns one :class:`LLMDependencyPrediction` per pair, in the same
        order as the input sequence.

        The caller is responsible for chunking large sequences into
        provider-sized batches before calling this method.

        Raises :class:`ValueError` if the provider response is malformed or
        any individual prediction fails validation.
        """

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Infer N-way basket groupings for a topic group of markets.

        Returns a list of :class:`LLMBasketGroup` objects, each identifying a
        set of markets whose combined YES tokens form a complete outcome set
        (probabilities summing toward 1.0).

        Providers that do not support basket inference should return ``[]``.
        """
        return []
