"""Tests for LLM basket-structure inference.

Covers the four areas required by the task:

1. LLM basket-structure responses are parsed correctly.
2. Malformed basket-structure responses are rejected.
3. The basket builder produces baskets that actually reflect the
   LLM-inferred grouping (not just pairwise propagation).
4. Existing convergence invariants still hold when baskets come from
   the LLM basket-group path.
"""
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
from polymarket_discovery.interfaces.llm_basket_group import LLMBasketGroup
from polymarket_discovery.providers.llm_codec import (
    build_basket_prompt,
    parse_llm_basket_groups,
    validate_llm_basket_groups,
)
from polymarket_discovery.providers.llm_stub import DeepSeekLLMProviderStub
from polymarket_discovery.stages.basket_builder import DefaultBasketBuilder
from polymarket_discovery.stages.basket_validator import DefaultBasketValidator
from polymarket_discovery.serialization import validate_output_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _market(market_id: str, token_ids: list[str], topic: str = "election") -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Will candidate {market_id} win?",
        description=f"Election market for {market_id}",
        rules="Standard rules",
        end_date="2026-11-03",
        topic=topic,
        token_ids=token_ids,
    )


def _basket_response(*groups: dict) -> str:
    """Build a valid LLM basket-group JSON string."""
    return json.dumps({"baskets": list(groups)})


def _valid_group(
    basket_id: str = "election-2026",
    market_ids: list[str] | None = None,
    rationale: str = "Four candidates; exactly one wins",
) -> dict:
    return {
        "basket_id": basket_id,
        "market_ids": market_ids or ["m1", "m2", "m3", "m4"],
        "rationale": rationale,
    }


# ---------------------------------------------------------------------------
# 1. Parse valid basket-structure responses
# ---------------------------------------------------------------------------


class TestParseValidResponses:
    def test_parses_single_basket_group(self) -> None:
        raw = _basket_response(_valid_group())
        groups = parse_llm_basket_groups(raw)
        assert len(groups) == 1
        assert groups[0].basket_id == "election-2026"
        assert groups[0].market_ids == ["m1", "m2", "m3", "m4"]
        assert groups[0].rationale == "Four candidates; exactly one wins"

    def test_parses_multiple_basket_groups(self) -> None:
        raw = _basket_response(
            _valid_group("basket-a", ["m1", "m2"], "Rationale A"),
            _valid_group("basket-b", ["m3", "m4"], "Rationale B"),
        )
        groups = parse_llm_basket_groups(raw)
        assert len(groups) == 2
        assert groups[0].basket_id == "basket-a"
        assert groups[1].basket_id == "basket-b"

    def test_parses_empty_baskets_array(self) -> None:
        raw = json.dumps({"baskets": []})
        groups = parse_llm_basket_groups(raw)
        assert groups == []

    def test_parse_accepts_dict_payload(self) -> None:
        payload = {"baskets": [_valid_group()]}
        groups = parse_llm_basket_groups(payload)
        assert len(groups) == 1

    def test_parse_strips_whitespace_from_string_fields(self) -> None:
        raw = json.dumps({
            "baskets": [{
                "basket_id": "  election-2026  ",
                "market_ids": ["  m1  ", "  m2  "],
                "rationale": "  valid rationale  ",
            }]
        })
        groups = parse_llm_basket_groups(raw)
        assert groups[0].basket_id == "election-2026"
        assert groups[0].market_ids == ["m1", "m2"]
        assert groups[0].rationale == "valid rationale"

    def test_parse_validates_market_ids_against_known_set(self) -> None:
        raw = _basket_response(_valid_group(market_ids=["m1", "m2"]))
        groups = parse_llm_basket_groups(raw, known_market_ids=frozenset({"m1", "m2", "m3"}))
        assert len(groups) == 1

    def test_parse_two_market_group_is_valid(self) -> None:
        raw = _basket_response(_valid_group(market_ids=["m1", "m2"]))
        groups = parse_llm_basket_groups(raw)
        assert len(groups) == 1
        assert groups[0].market_ids == ["m1", "m2"]


# ---------------------------------------------------------------------------
# 2. Reject malformed basket-structure responses
# ---------------------------------------------------------------------------


class TestRejectMalformedResponses:
    def test_rejects_non_json_string(self) -> None:
        with pytest.raises(ValueError, match="valid JSON"):
            parse_llm_basket_groups("not json at all")

    def test_rejects_json_array_at_root(self) -> None:
        with pytest.raises(ValueError, match="JSON object"):
            parse_llm_basket_groups("[]")

    def test_rejects_missing_baskets_key(self) -> None:
        with pytest.raises(ValueError, match='"baskets" array'):
            parse_llm_basket_groups('{"groups": []}')

    def test_rejects_baskets_as_non_array(self) -> None:
        with pytest.raises(ValueError, match='"baskets" array'):
            parse_llm_basket_groups('{"baskets": "not-an-array"}')

    def test_rejects_basket_item_as_non_object(self) -> None:
        with pytest.raises(ValueError, match="baskets\\[0\\]"):
            parse_llm_basket_groups('{"baskets": ["not-an-object"]}')

    def test_rejects_empty_basket_id(self) -> None:
        raw = _basket_response({
            "basket_id": "",
            "market_ids": ["m1", "m2"],
            "rationale": "valid",
        })
        with pytest.raises(ValueError, match="basket_id"):
            parse_llm_basket_groups(raw)

    def test_rejects_duplicate_basket_ids(self) -> None:
        raw = _basket_response(
            _valid_group("same-id", ["m1", "m2"]),
            _valid_group("same-id", ["m3", "m4"]),
        )
        with pytest.raises(ValueError, match="duplicate"):
            parse_llm_basket_groups(raw)

    def test_rejects_single_market_group(self) -> None:
        raw = _basket_response({
            "basket_id": "solo",
            "market_ids": ["m1"],
            "rationale": "only one market",
        })
        with pytest.raises(ValueError, match="at least 2"):
            parse_llm_basket_groups(raw)

    def test_rejects_empty_market_ids_list(self) -> None:
        raw = _basket_response({
            "basket_id": "empty",
            "market_ids": [],
            "rationale": "no markets",
        })
        with pytest.raises(ValueError, match="at least 2"):
            parse_llm_basket_groups(raw)

    def test_rejects_duplicate_market_ids_within_group(self) -> None:
        raw = _basket_response({
            "basket_id": "dup",
            "market_ids": ["m1", "m1"],
            "rationale": "same market twice",
        })
        with pytest.raises(ValueError, match="duplicate market_id"):
            parse_llm_basket_groups(raw)

    def test_rejects_empty_rationale(self) -> None:
        raw = _basket_response({
            "basket_id": "no-rationale",
            "market_ids": ["m1", "m2"],
            "rationale": "",
        })
        with pytest.raises(ValueError, match="rationale"):
            parse_llm_basket_groups(raw)

    def test_rejects_market_id_not_in_known_set(self) -> None:
        raw = _basket_response(_valid_group(market_ids=["m1", "unknown-99"]))
        with pytest.raises(ValueError, match="unknown market IDs"):
            parse_llm_basket_groups(raw, known_market_ids=frozenset({"m1", "m2"}))

    def test_rejects_non_string_market_id(self) -> None:
        raw = json.dumps({
            "baskets": [{
                "basket_id": "bad-ids",
                "market_ids": ["m1", 42],
                "rationale": "contains integer",
            }]
        })
        with pytest.raises(ValueError, match="non-string"):
            parse_llm_basket_groups(raw)


# ---------------------------------------------------------------------------
# 3. Basket builder produces baskets from LLM-inferred groupings
# ---------------------------------------------------------------------------


class TestBasketBuilderGroupPath:
    """The builder must reflect the LLM grouping, not just pairwise edges."""

    def test_builder_creates_basket_from_four_market_llm_group(self) -> None:
        """An N-way (4-market) LLM group produces a single basket covering all tokens."""
        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
            _market("m3", ["tok-m3"]),
            _market("m4", ["tok-m4"]),
        ]
        groups = [
            LLMBasketGroup(
                basket_id="election-2026",
                market_ids=["m1", "m2", "m3", "m4"],
                rationale="Four candidates; exactly one wins",
            )
        ]

        baskets, synthetic_edges = DefaultBasketBuilder().build(
            markets, dependencies=[], basket_groups=groups
        )

        assert len(baskets) == 1
        basket = baskets[0]
        assert basket.basket_id == "election-2026"
        assert set(basket.token_ids) == {"tok-m1", "tok-m2", "tok-m3", "tok-m4"}
        assert basket.expected_sum == 1.0
        # dependency_basis must be non-empty and reference synthetic edges
        assert len(basket.dependency_basis) >= 1
        # 3 synthetic edges for a 4-market chain (m1-m2, m2-m3, m3-m4)
        assert len(synthetic_edges) == 3

    def test_builder_ignores_pairwise_edges_when_basket_groups_are_provided(self) -> None:
        """When basket_groups are non-empty, pairwise edges are NOT used."""
        from polymarket_discovery.contracts import DependencyEdge

        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
        ]
        pairwise_edges = [
            DependencyEdge(
                edge_id="m1__m2",
                edge_type="mutually_exclusive",
                from_market_id="m1",
                to_market_id="m2",
                confidence=0.99,
                rationale="pairwise edge — should be ignored",
            )
        ]
        groups = [
            LLMBasketGroup(
                basket_id="llm-basket",
                market_ids=["m1", "m2"],
                rationale="LLM-inferred group",
            )
        ]

        baskets, synthetic_edges = DefaultBasketBuilder().build(
            markets, dependencies=pairwise_edges, basket_groups=groups
        )

        # Basket comes from the LLM group, not the pairwise edge
        assert len(baskets) == 1
        assert baskets[0].basket_id == "llm-basket"
        # Synthetic edge ID derives from the group, not the pairwise edge
        assert all(e.edge_id.startswith("basket-member__") for e in synthetic_edges)

    def test_builder_uses_pairwise_fallback_when_no_basket_groups(self) -> None:
        """When basket_groups is empty, the pairwise-edge path is used."""
        from polymarket_discovery.contracts import DependencyEdge

        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
        ]
        pairwise_edges = [
            DependencyEdge(
                edge_id="m1__m2",
                edge_type="mutually_exclusive",
                from_market_id="m1",
                to_market_id="m2",
                confidence=0.99,
                rationale="high confidence pairwise",
            )
        ]

        baskets, synthetic_edges = DefaultBasketBuilder().build(
            markets, dependencies=pairwise_edges, basket_groups=[]
        )

        assert len(baskets) == 1
        assert baskets[0].basket_id == "basket-m1__m2"
        assert synthetic_edges == []

    def test_builder_skips_group_when_market_id_not_found(self) -> None:
        """Groups referencing unknown markets are silently skipped."""
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        groups = [
            LLMBasketGroup(
                basket_id="bad-group",
                market_ids=["m1", "unknown-99"],
                rationale="one market is unknown",
            )
        ]

        baskets, synthetic_edges = DefaultBasketBuilder().build(
            markets, dependencies=[], basket_groups=groups
        )

        # Only m1 resolves; group of 1 market is skipped
        assert baskets == []
        assert synthetic_edges == []

    def test_builder_deduplicates_token_ids_within_group_basket(self) -> None:
        """Shared token IDs across group markets appear only once in the basket."""
        markets = [
            _market("m1", ["tok-shared", "tok-m1-only"]),
            _market("m2", ["tok-shared", "tok-m2-only"]),
        ]
        groups = [
            LLMBasketGroup(
                basket_id="dedup-test",
                market_ids=["m1", "m2"],
                rationale="test deduplication",
            )
        ]

        baskets, _ = DefaultBasketBuilder().build(
            markets, dependencies=[], basket_groups=groups
        )

        assert len(baskets) == 1
        assert baskets[0].token_ids.count("tok-shared") == 1


# ---------------------------------------------------------------------------
# 4. Convergence invariants hold for LLM-inferred baskets
# ---------------------------------------------------------------------------


class TestConvergenceInvariantsWithLLMBaskets:
    """The three invariants from test_convergence_invariants.py must hold
    even when baskets are produced by the LLM basket-group path."""

    def test_expected_sum_is_1_0_for_llm_inferred_basket(self) -> None:
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        groups = [LLMBasketGroup("b1", ["m1", "m2"], "rationale")]

        baskets, _ = DefaultBasketBuilder().build(markets, [], basket_groups=groups)

        assert len(baskets) == 1
        assert baskets[0].expected_sum == 1.0

    def test_validator_accepts_llm_inferred_basket(self) -> None:
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        groups = [LLMBasketGroup("b1", ["m1", "m2"], "rationale")]

        baskets, _ = DefaultBasketBuilder().build(markets, [], basket_groups=groups)

        # Must not raise.
        DefaultBasketValidator().validate(baskets)

    def test_validator_rejects_overlap_across_two_llm_groups(self) -> None:
        """Two LLM groups that share a market (and thus a token) must fail validation."""
        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
            _market("m3", ["tok-m3"]),
        ]
        groups = [
            LLMBasketGroup("basket-ab", ["m1", "m2"], "group 1"),
            LLMBasketGroup("basket-bc", ["m2", "m3"], "group 2 — m2 is shared"),
        ]

        baskets, _ = DefaultBasketBuilder().build(markets, [], basket_groups=groups)

        with pytest.raises(ValueError, match="shares token ids"):
            DefaultBasketValidator().validate(baskets)

    def test_schema_validation_passes_for_complete_llm_basket(self) -> None:
        """The serialized document must pass schema + cross-entity validation."""
        from polymarket_discovery.contracts import RunMetadata, ArbitrageOutputDocument
        from polymarket_discovery.serialization import to_output_dict

        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
            _market("m3", ["tok-m3"]),
        ]
        groups = [LLMBasketGroup("election-basket", ["m1", "m2", "m3"], "three candidates")]

        baskets, synthetic_edges = DefaultBasketBuilder().build(markets, [], basket_groups=groups)

        run_metadata = RunMetadata(
            run_id="test-llm-basket-run",
            generated_at_utc="2026-05-02T00:00:00Z",
            market_source="fixture",
            embedding_model="stub",
            llm_model="stub",
        )
        document = ArbitrageOutputDocument(
            run_metadata=run_metadata,
            markets=markets,
            dependencies=synthetic_edges,
            baskets=baskets,
        )
        payload = to_output_dict(document)
        # Must not raise.
        validate_output_document(payload)


# ---------------------------------------------------------------------------
# 5. Stub provider emits realistic basket-structure examples
# ---------------------------------------------------------------------------


class TestStubProviderBasketGroups:
    def test_stub_returns_single_basket_covering_all_markets(self) -> None:
        stub = DeepSeekLLMProviderStub()
        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
            _market("m3", ["tok-m3"]),
        ]

        groups = stub.infer_basket_groups(markets)

        assert len(groups) == 1
        assert set(groups[0].market_ids) == {"m1", "m2", "m3"}
        assert groups[0].rationale  # non-empty

    def test_stub_returns_empty_for_single_market(self) -> None:
        stub = DeepSeekLLMProviderStub()
        groups = stub.infer_basket_groups([_market("m1", ["tok-m1"])])
        assert groups == []

    def test_stub_basket_id_is_deterministic(self) -> None:
        stub = DeepSeekLLMProviderStub()
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        groups_a = stub.infer_basket_groups(markets)
        groups_b = stub.infer_basket_groups(markets)
        assert groups_a[0].basket_id == groups_b[0].basket_id


# ---------------------------------------------------------------------------
# 6. build_basket_prompt tests
# ---------------------------------------------------------------------------


class TestBuildBasketPrompt:
    def test_prompt_includes_all_market_ids(self) -> None:
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        prompt = build_basket_prompt(markets)
        payload = json.loads(prompt)
        market_ids_in_prompt = [m["market_id"] for m in payload["markets"]]
        assert "m1" in market_ids_in_prompt
        assert "m2" in market_ids_in_prompt

    def test_prompt_is_deterministic(self) -> None:
        markets = [_market("m1", ["tok-m1"]), _market("m2", ["tok-m2"])]
        assert build_basket_prompt(markets) == build_basket_prompt(markets)

    def test_prompt_contains_question_text(self) -> None:
        markets = [_market("alice", ["tok-a"]), _market("bob", ["tok-b"])]
        prompt = build_basket_prompt(markets)
        assert "alice" in prompt or "candidate alice" in prompt.lower()


# ---------------------------------------------------------------------------
# 7. LLMDependencyInferencer.infer_basket_groups integration
# ---------------------------------------------------------------------------


class TestLLMDependencyInferencerBasketGroups:
    def test_infer_basket_groups_uses_stub_provider(self) -> None:
        from polymarket_discovery.stages.dependency_inferencer import LLMDependencyInferencer

        stub = DeepSeekLLMProviderStub()
        inferencer = LLMDependencyInferencer(llm_provider=stub)
        markets = [
            _market("m1", ["tok-m1"]),
            _market("m2", ["tok-m2"]),
            _market("m3", ["tok-m3"]),
        ]

        groups = inferencer.infer_basket_groups(markets)

        assert len(groups) == 1
        assert set(groups[0].market_ids) == {"m1", "m2", "m3"}

    def test_infer_basket_groups_returns_empty_for_single_market(self) -> None:
        from polymarket_discovery.stages.dependency_inferencer import LLMDependencyInferencer

        stub = DeepSeekLLMProviderStub()
        inferencer = LLMDependencyInferencer(llm_provider=stub)

        groups = inferencer.infer_basket_groups([_market("m1", ["tok-m1"])])

        assert groups == []


# ---------------------------------------------------------------------------
# 8. Basket grouping buckets by (topic, canonical_end_date), not topic alone
# ---------------------------------------------------------------------------


class TestGroupMarketsForBasketInference:
    """_group_markets_for_basket_inference must never mix markets from different
    end dates into the same bucket, even when they share a topic.

    This is the correctness fix for the bug where basket inference was called
    per topic bucket only — markets resolving at different times cannot satisfy
    the convergence-to-1.00 invariant and therefore must not appear in the
    same basket group.
    """

    def _market_with_end_date(
        self,
        market_id: str,
        end_date: str,
        topic: str = "election",
    ) -> MarketDescriptor:
        return MarketDescriptor(
            market_id=market_id,
            condition_id=f"cond-{market_id}",
            question=f"Will candidate {market_id} win?",
            description=f"Election market for {market_id}",
            rules="Standard rules",
            end_date=end_date,
            topic=topic,
            token_ids=[f"tok-{market_id}"],
        )

    def test_same_topic_different_end_dates_produce_separate_buckets(self) -> None:
        """Markets sharing a topic but with different end dates must land in
        separate (topic, end_date) buckets — never in the same basket group."""
        from polymarket_discovery.stages.stages import _group_markets_for_basket_inference

        markets = [
            self._market_with_end_date("m1", "2026-11-03", topic="election"),
            self._market_with_end_date("m2", "2026-11-03", topic="election"),
            self._market_with_end_date("m3", "2027-11-03", topic="election"),
            self._market_with_end_date("m4", "2027-11-03", topic="election"),
        ]

        buckets = _group_markets_for_basket_inference(markets)

        # Must produce exactly two buckets (one per end date), not one big bucket
        assert len(buckets) == 2

        # Each bucket must contain only markets sharing the same end date
        for bucket in buckets:
            end_dates = {m.end_date for m in bucket}
            assert len(end_dates) == 1, (
                f"Bucket contains markets from multiple end dates: {end_dates}"
            )

        # No single bucket should span both end dates
        all_bucket_market_ids = [
            frozenset(m.market_id for m in bucket) for bucket in buckets
        ]
        assert frozenset({"m1", "m2"}) in all_bucket_market_ids
        assert frozenset({"m3", "m4"}) in all_bucket_market_ids

    def test_same_topic_same_end_date_produces_single_bucket(self) -> None:
        """Markets sharing both topic and end date remain in the same bucket."""
        from polymarket_discovery.stages.stages import _group_markets_for_basket_inference

        markets = [
            self._market_with_end_date("m1", "2026-11-03T23:59:59Z", topic="election"),
            self._market_with_end_date("m2", "2026-11-03", topic="election"),
        ]

        buckets = _group_markets_for_basket_inference(markets)

        # Both markets canonicalize to 2026-11-03 — they belong together
        assert len(buckets) == 1
        assert {m.market_id for m in buckets[0]} == {"m1", "m2"}

    def test_cross_end_date_basket_never_produced_by_stages_pipeline(self) -> None:
        """End-to-end: run_pipeline in stages.py must not call infer_basket_groups
        with a mix of markets from different end dates."""
        import json
        import tempfile
        from pathlib import Path
        from polymarket_discovery.stages.dependency_inferencer import LLMDependencyInferencer
        from polymarket_discovery.stages.basket_builder import DefaultBasketBuilder
        from polymarket_discovery.stages.basket_validator import DefaultBasketValidator
        from polymarket_discovery.stages.topic_assigner import DefaultTopicAssigner
        from polymarket_discovery.stages.candidate_reducer import TopicEndDateCandidateReducer
        from polymarket_discovery.stages.stages import run_pipeline
        from polymarket_discovery.contracts import RunMetadata

        # Capture which market groups the LLM is asked about
        seen_groups: list[list[str]] = []

        class CapturingStub(DeepSeekLLMProviderStub):
            def infer_basket_groups(self, markets, config=None):  # type: ignore[override]
                seen_groups.append([m.market_id for m in markets])
                return super().infer_basket_groups(markets)

        stub = CapturingStub()
        inferencer = LLMDependencyInferencer(llm_provider=stub)

        markets = [
            self._market_with_end_date("m1", "2026-11-03", topic="election"),
            self._market_with_end_date("m2", "2026-11-03", topic="election"),
            self._market_with_end_date("m3", "2027-11-03", topic="election"),
            self._market_with_end_date("m4", "2027-11-03", topic="election"),
        ]

        # Use a stub topic assigner that preserves the pre-assigned topics
        class PassthroughTopicAssigner(DefaultTopicAssigner):
            def assign_topics(self, mkts, config=None):  # type: ignore[override]
                return list(mkts)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = Path(f.name)

        run_pipeline(
            markets=markets,
            run_metadata=RunMetadata(
                run_id="test-end-date-bucketing",
                generated_at_utc="2026-05-02T00:00:00Z",
                market_source="fixture",
                embedding_model="stub",
                llm_model="stub",
            ),
            topic_assigner=PassthroughTopicAssigner(),
            candidate_reducer=TopicEndDateCandidateReducer(),
            dependency_inferencer=inferencer,
            basket_builder=DefaultBasketBuilder(),
            basket_validator=DefaultBasketValidator(),
            output_path=output_path,
        )

        # The LLM must never be called with markets from different end dates
        for group in seen_groups:
            group_markets = [m for m in markets if m.market_id in group]
            end_dates = {m.end_date for m in group_markets}
            assert len(end_dates) <= 1, (
                f"infer_basket_groups was called with markets from multiple end dates: "
                f"{end_dates} — group {group}"
            )
