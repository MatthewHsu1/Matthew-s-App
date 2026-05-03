from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.stages import TopicEndDateCandidateReducer


def _market(market_id: str, topic: str, end_date: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Question {market_id}",
        description="desc",
        end_date=end_date,
        topic=topic,
        token_ids=[f"tok-{market_id}"],
    )


def test_candidate_reducer_gates_by_topic_and_canonical_end_date() -> None:
    reducer = TopicEndDateCandidateReducer()
    markets = [
        _market("m1", "election", "2026-11-03T23:59:59Z"),
        _market("m2", "election", "2026-11-03"),
        _market("m3", "election", "2026-12-01"),
        _market("m4", "economy", "2026-11-03"),
    ]

    pairs = reducer.reduce(markets)
    reduced_ids = {(left.market_id, right.market_id) for left, right in pairs}

    assert reduced_ids == {("m1", "m2")}
