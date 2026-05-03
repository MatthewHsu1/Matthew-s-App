"""Tests proving the three convergence-contract invariants introduced to
enforce the Phase 1 goal: baskets whose combined pricing converges toward 1.00.

Rule 1 — expected_sum must equal 1.0 (within tolerance 1e-9)
Rule 2 — basket token_ids must cover the complete outcome set of the
          participating markets (no tokens missing)
Rule 3 — no two baskets in the same document may share a token ID
          (no double-allocated capital)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.contracts import BasketItem
from polymarket_discovery.serialization import OutputValidationError, validate_output_document
from polymarket_discovery.stages import DefaultBasketValidator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _minimal_document(baskets: list[dict]) -> dict:
    """Build a minimal valid ArbitrageOutputDocument dict, substituting the
    provided baskets list.  Markets m1 and m2 each have two tokens (YES/NO)
    so the full outcome set for a basket built from both is 4 tokens."""
    return {
        "schema_version": "v1",
        "run_metadata": {
            "schema_version": "v1",
            "run_id": "test-run",
            "generated_at_utc": "2026-05-01T00:00:00Z",
            "market_source": "fixture",
            "embedding_model": "stub",
            "llm_model": "stub",
        },
        "markets": [
            {
                "market_id": "m1",
                "condition_id": "cond-m1",
                "question": "Will A win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-a-yes", "tok-a-no"],
            },
            {
                "market_id": "m2",
                "condition_id": "cond-m2",
                "question": "Will B win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-b-yes", "tok-b-no"],
            },
        ],
        "dependencies": [
            {
                "edge_id": "m1__m2",
                "edge_type": "mutually_exclusive",
                "from_market_id": "m1",
                "to_market_id": "m2",
                "confidence": 0.95,
                "rationale": "test fixture",
            }
        ],
        "baskets": baskets,
    }


def _full_basket(basket_id: str = "basket-m1__m2") -> dict:
    """A complete basket covering all four outcome tokens of m1+m2."""
    return {
        "basket_id": basket_id,
        "token_ids": ["tok-a-yes", "tok-a-no", "tok-b-yes", "tok-b-no"],
        "expected_sum": 1.0,
        "dependency_basis": ["m1__m2"],
    }


# ---------------------------------------------------------------------------
# Rule 1: expected_sum must equal 1.0
# ---------------------------------------------------------------------------

class TestExpectedSumRule:
    """expected_sum must be exactly 1.0 (within 1e-9 tolerance)."""

    def test_validator_rejects_expected_sum_zero(self) -> None:
        """0.0 is > 0 but was previously allowed — must now be rejected."""
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=0.0,
            dependency_basis=["edge-1"],
        )
        with pytest.raises(ValueError, match="expected_sum"):
            DefaultBasketValidator().validate([basket])

    def test_validator_rejects_expected_sum_half(self) -> None:
        """0.5 passes the old > 0 gate but fails the new == 1.0 check."""
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=0.5,
            dependency_basis=["edge-1"],
        )
        with pytest.raises(ValueError, match="expected_sum"):
            DefaultBasketValidator().validate([basket])

    def test_validator_rejects_expected_sum_two(self) -> None:
        """Values > 1.0 are also invalid."""
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=2.0,
            dependency_basis=["edge-1"],
        )
        with pytest.raises(ValueError, match="expected_sum"):
            DefaultBasketValidator().validate([basket])

    def test_validator_rejects_nan_expected_sum(self) -> None:
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=float("nan"),
            dependency_basis=["edge-1"],
        )
        with pytest.raises(ValueError, match="expected_sum"):
            DefaultBasketValidator().validate([basket])

    def test_validator_accepts_expected_sum_exactly_one(self) -> None:
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=1.0,
            dependency_basis=["edge-1"],
        )
        # Should not raise.
        DefaultBasketValidator().validate([basket])

    def test_validator_accepts_expected_sum_within_tolerance(self) -> None:
        """Values within 1e-9 of 1.0 should be accepted."""
        basket = BasketItem(
            basket_id="b1",
            token_ids=["tok-a"],
            expected_sum=1.0 + 1e-10,
            dependency_basis=["edge-1"],
        )
        DefaultBasketValidator().validate([basket])

    def test_schema_rejects_expected_sum_not_one(self) -> None:
        """The serialized document schema also enforces expected_sum == 1.0."""
        doc = _minimal_document([
            {
                "basket_id": "basket-m1__m2",
                "token_ids": ["tok-a-yes", "tok-a-no", "tok-b-yes", "tok-b-no"],
                "expected_sum": 0.5,
                "dependency_basis": ["m1__m2"],
            }
        ])
        with pytest.raises((ValueError, OutputValidationError)):
            validate_output_document(doc)


# ---------------------------------------------------------------------------
# Rule 2: completeness check — basket must cover the full outcome set
# ---------------------------------------------------------------------------

class TestCompletenessRule:
    """A basket must contain all token IDs from its participating markets."""

    def test_serialization_rejects_basket_missing_yes_token(self) -> None:
        """Basket contains only NO tokens — YES tokens are missing."""
        doc = _minimal_document([
            {
                "basket_id": "basket-m1__m2",
                "token_ids": ["tok-a-no", "tok-b-no"],
                "expected_sum": 1.0,
                "dependency_basis": ["m1__m2"],
            }
        ])
        with pytest.raises((ValueError, OutputValidationError), match="incomplete outcome set"):
            validate_output_document(doc)

    def test_serialization_rejects_basket_with_only_one_market_tokens(self) -> None:
        """Basket contains tokens from m1 only — m2 tokens are absent."""
        doc = _minimal_document([
            {
                "basket_id": "basket-m1__m2",
                "token_ids": ["tok-a-yes", "tok-a-no"],
                "expected_sum": 1.0,
                "dependency_basis": ["m1__m2"],
            }
        ])
        with pytest.raises((ValueError, OutputValidationError), match="incomplete outcome set"):
            validate_output_document(doc)

    def test_serialization_accepts_complete_basket(self) -> None:
        """Basket with all four tokens for m1+m2 passes the completeness gate."""
        doc = _minimal_document([_full_basket()])
        validate_output_document(doc)  # must not raise

    def test_serialization_accepts_empty_baskets_list(self) -> None:
        """Empty basket list is still valid — no completeness violations."""
        doc = _minimal_document([])
        validate_output_document(doc)  # must not raise


# ---------------------------------------------------------------------------
# Rule 3: cross-basket overlap — no two baskets may share a token ID
# ---------------------------------------------------------------------------

class TestOverlapRule:
    """No two baskets in the same document may share a token ID."""

    def test_validator_rejects_two_baskets_sharing_a_token(self) -> None:
        basket_a = BasketItem(
            basket_id="b1",
            token_ids=["tok-shared", "tok-only-a"],
            expected_sum=1.0,
            dependency_basis=["edge-1"],
        )
        basket_b = BasketItem(
            basket_id="b2",
            token_ids=["tok-shared", "tok-only-b"],
            expected_sum=1.0,
            dependency_basis=["edge-2"],
        )
        with pytest.raises(ValueError, match="shares token ids"):
            DefaultBasketValidator().validate([basket_a, basket_b])

    def test_validator_accepts_non_overlapping_baskets(self) -> None:
        basket_a = BasketItem(
            basket_id="b1",
            token_ids=["tok-a1", "tok-a2"],
            expected_sum=1.0,
            dependency_basis=["edge-1"],
        )
        basket_b = BasketItem(
            basket_id="b2",
            token_ids=["tok-b1", "tok-b2"],
            expected_sum=1.0,
            dependency_basis=["edge-2"],
        )
        # Should not raise.
        DefaultBasketValidator().validate([basket_a, basket_b])

    def test_serialization_rejects_two_baskets_sharing_token(self) -> None:
        """Two baskets in the same document sharing a token are rejected at
        the serialization cross-entity consistency gate."""
        # To construct this without hitting the completeness rule, we need
        # two markets that each have a single token, and one basket covers
        # market m1 fully while the second basket also references m1's token.
        # We use a second dependency edge to give the second basket a valid
        # dependency_basis.  We add a third market m3 with a single token so
        # the second basket can be "complete" while still sharing tok-a-yes.
        doc: dict = {
            "schema_version": "v1",
            "run_metadata": {
                "schema_version": "v1",
                "run_id": "test-overlap",
                "generated_at_utc": "2026-05-01T00:00:00Z",
                "market_source": "fixture",
                "embedding_model": "stub",
                "llm_model": "stub",
            },
            "markets": [
                {
                    "market_id": "m1",
                    "condition_id": "cond-m1",
                    "question": "Will A win?",
                    "description": "",
                    "end_date": "2026-11-03",
                    "topic": "topic-01",
                    "token_ids": ["tok-a"],
                },
                {
                    "market_id": "m2",
                    "condition_id": "cond-m2",
                    "question": "Will B win?",
                    "description": "",
                    "end_date": "2026-11-03",
                    "topic": "topic-01",
                    "token_ids": ["tok-b"],
                },
                {
                    "market_id": "m3",
                    "condition_id": "cond-m3",
                    "question": "Will C win?",
                    "description": "",
                    "end_date": "2026-11-03",
                    "topic": "topic-01",
                    "token_ids": ["tok-a"],  # same token as m1
                },
            ],
            "dependencies": [
                {
                    "edge_id": "m1__m2",
                    "edge_type": "mutually_exclusive",
                    "from_market_id": "m1",
                    "to_market_id": "m2",
                    "confidence": 0.95,
                    "rationale": "test",
                },
                {
                    "edge_id": "m1__m3",
                    "edge_type": "mutually_exclusive",
                    "from_market_id": "m1",
                    "to_market_id": "m3",
                    "confidence": 0.95,
                    "rationale": "test",
                },
            ],
            "baskets": [
                {
                    "basket_id": "basket-1",
                    "token_ids": ["tok-a", "tok-b"],
                    "expected_sum": 1.0,
                    "dependency_basis": ["m1__m2"],
                },
                {
                    "basket_id": "basket-2",
                    # tok-a appears in both m1 and m3, so it is within the
                    # allowed set for the m1__m3 edge — but it was already
                    # claimed by basket-1.
                    "token_ids": ["tok-a"],
                    "expected_sum": 1.0,
                    "dependency_basis": ["m1__m3"],
                },
            ],
        }
        with pytest.raises((ValueError, OutputValidationError), match="overlapping outcome sets"):
            validate_output_document(doc)

    def test_serialization_accepts_non_overlapping_baskets(self) -> None:
        """Two baskets with fully disjoint token sets pass the overlap gate."""
        # Use four single-token markets so each basket is "complete" for its
        # pair while having no shared tokens.
        doc: dict = {
            "schema_version": "v1",
            "run_metadata": {
                "schema_version": "v1",
                "run_id": "test-no-overlap",
                "generated_at_utc": "2026-05-01T00:00:00Z",
                "market_source": "fixture",
                "embedding_model": "stub",
                "llm_model": "stub",
            },
            "markets": [
                {"market_id": "m1", "condition_id": "c1", "question": "Q1", "description": "", "end_date": "2026-11-03", "topic": "t1", "token_ids": ["tok-a"]},
                {"market_id": "m2", "condition_id": "c2", "question": "Q2", "description": "", "end_date": "2026-11-03", "topic": "t1", "token_ids": ["tok-b"]},
                {"market_id": "m3", "condition_id": "c3", "question": "Q3", "description": "", "end_date": "2026-11-03", "topic": "t1", "token_ids": ["tok-c"]},
                {"market_id": "m4", "condition_id": "c4", "question": "Q4", "description": "", "end_date": "2026-11-03", "topic": "t1", "token_ids": ["tok-d"]},
            ],
            "dependencies": [
                {"edge_id": "e1", "edge_type": "mutually_exclusive", "from_market_id": "m1", "to_market_id": "m2", "confidence": 0.95, "rationale": ""},
                {"edge_id": "e2", "edge_type": "mutually_exclusive", "from_market_id": "m3", "to_market_id": "m4", "confidence": 0.95, "rationale": ""},
            ],
            "baskets": [
                {"basket_id": "basket-1", "token_ids": ["tok-a", "tok-b"], "expected_sum": 1.0, "dependency_basis": ["e1"]},
                {"basket_id": "basket-2", "token_ids": ["tok-c", "tok-d"], "expected_sum": 1.0, "dependency_basis": ["e2"]},
            ],
        }
        validate_output_document(doc)  # must not raise
