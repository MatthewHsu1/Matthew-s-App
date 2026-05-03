from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.providers.llm_codec import (
    ALLOWED_LLM_EDGE_TYPES,
    build_dependency_prompt,
    parse_llm_dependency_prediction,
    validate_llm_dependency_prediction,
)


def _market(market_id: str, question: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=question,
        description=f"desc-{market_id}",
        rules=f"rules-{market_id}",
        end_date="2026-11-03",
        topic="election",
        token_ids=[f"tok-{market_id}"],
    )


def test_allowed_edge_types_exposes_canonical_set() -> None:
    assert ALLOWED_LLM_EDGE_TYPES == frozenset(
        {"mutually_exclusive", "conditional", "related"}
    )


def test_build_dependency_prompt_returns_deterministic_sorted_json() -> None:
    left = _market("m1", "Will A win?")
    right = _market("m2", "Will B win?")

    prompt = build_dependency_prompt(left, right)

    payload = json.loads(prompt)
    assert set(payload.keys()) == {"left_market", "right_market"}
    assert payload["left_market"]["market_id"] == "m1"
    assert payload["left_market"]["question"] == "Will A win?"
    assert payload["left_market"]["description"] == "desc-m1"
    assert payload["left_market"]["rules"] == "rules-m1"
    assert payload["left_market"]["end_date"] == "2026-11-03"
    assert payload["left_market"]["topic"] == "election"
    assert payload["right_market"]["market_id"] == "m2"
    assert payload["right_market"]["question"] == "Will B win?"

    # Determinism: keys are sorted, so the same inputs produce identical output.
    assert build_dependency_prompt(left, right) == prompt


def test_build_dependency_prompt_keys_are_sorted() -> None:
    left = _market("m1", "L?")
    right = _market("m2", "R?")
    prompt = build_dependency_prompt(left, right)

    # sort_keys=True means top-level "left_market" precedes "right_market".
    assert prompt.index('"left_market"') < prompt.index('"right_market"')


def test_parse_llm_dependency_prediction_round_trips_clean_json() -> None:
    prediction = parse_llm_dependency_prediction(
        '{"edge_type":"related","confidence":0.5,"rationale":"shared event"}'
    )
    assert prediction.edge_type == "related"
    assert prediction.confidence == pytest.approx(0.5)
    assert prediction.rationale == "shared event"


def test_validate_llm_dependency_prediction_rejects_unknown_edge_type() -> None:
    from polymarket_discovery.interfaces.llm_dependency_prediction import (
        LLMDependencyPrediction,
    )

    with pytest.raises(ValueError, match="edge_type"):
        validate_llm_dependency_prediction(
            LLMDependencyPrediction(
                edge_type="basket", confidence=0.5, rationale="x"
            )
        )
