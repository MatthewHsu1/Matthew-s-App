from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from typing import Any

from ..contracts import MarketDescriptor
from ..interfaces.candidate_reducer import CandidateReducer
from ..interfaces.market_pair import MarketPair
from .topic_assigner import canonicalize_end_date


class TopicEndDateCandidateReducer(CandidateReducer):
    """Paper-aligned reducer: only compare markets sharing topic and end date."""

    def reduce(
        self,
        markets: Sequence[MarketDescriptor],
        config: Any | None = None,
    ) -> list[MarketPair]:
        buckets: dict[tuple[str, str], list[MarketDescriptor]] = {}

        for market in markets:
            topic_key = (market.topic or "").strip().lower()

            end_date_key = canonicalize_end_date(market.end_date)

            if not topic_key or not end_date_key:
                continue

            bucket_key = (topic_key, end_date_key)

            buckets.setdefault(bucket_key, []).append(market)

        pairs: list[MarketPair] = []

        for bucket_markets in buckets.values():
            for left, right in combinations(bucket_markets, 2):
                pairs.append((left, right))
                
        return pairs
