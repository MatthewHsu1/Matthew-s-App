from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..contracts import MarketDescriptor
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider
from ..interfaces.market_pair import MarketPair
from ..interfaces.openai_invoker import OpenAIInvoker
from .llm_codec import (
    build_basket_prompt,
    build_batched_dependency_prompt,
    parse_batched_dependency_predictions,
    parse_llm_basket_groups,
)
from .settings import LLMProviderSettings

_BASKET_SYSTEM_PROMPT = (
    "You identify basket structure in prediction markets. "
    "Given a list of markets that share a topic and end date, identify subsets "
    "whose YES-token prices sum to 1.0 (complete outcome sets). "
    'Reply with a single JSON object containing a "baskets" array. '
    "Each element must have basket_id (string), market_ids (array of market_id strings), "
    "and rationale (string). Only include markets that genuinely form a complete outcome set. "
    'Return {"baskets": []} if no complete sets are found.'
)

_BATCHED_DEPENDENCY_SYSTEM_PROMPT = (
    "You infer market dependencies. You will receive a JSON object with a 'pairs' array. "
    "Each pair has a pair_id, left_market, and right_market. "
    "Reply with a single JSON object containing a 'predictions' array. "
    "Each element must echo back the pair_id and include edge_type, confidence, and rationale. "
    "edge_type must be one of mutually_exclusive, conditional, related. "
    "confidence must be a number from 0 to 1. "
    "You MUST return exactly one prediction for every pair_id in the input, in any order."
)


@dataclass(slots=True)
class OpenAICompatibleLLMProvider(LLMProvider):
    settings: LLMProviderSettings
    invoker: OpenAIInvoker

    def infer_dependencies_batched(
        self,
        pairs: Sequence[MarketPair],
    ) -> list[LLMDependencyPrediction]:
        """Infer dependency metadata for a batch of market pairs in a single HTTP call."""
        if not pairs:
            return []
        result = self.invoker.call(
            {
                "model": self.settings.model_name,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": _BATCHED_DEPENDENCY_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": build_batched_dependency_prompt(pairs),
                    },
                ],
            }
        )
        return parse_batched_dependency_predictions(result.content, expected_count=len(pairs))

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Ask the LLM to identify N-way basket groupings for the given topic group."""
        if len(markets) < 2:
            return []
        known_ids = frozenset(m.market_id for m in markets)
        result = self.invoker.call(
            {
                "model": self.settings.model_name,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": _BASKET_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": build_basket_prompt(markets),
                    },
                ],
            }
        )
        return parse_llm_basket_groups(result.content, known_market_ids=known_ids)
