from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.contracts import BasketItem
from polymarket_discovery.contracts import DependencyEdge
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.stages import DefaultBasketBuilder
from polymarket_discovery.stages import DefaultBasketValidator


def _market(market_id: str, token_ids: list[str]) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Question {market_id}",
        description="Description",
        end_date="2026-11-03",
        topic="topic",
        token_ids=token_ids,
    )


def _edge(
    edge_id: str,
    from_market_id: str,
    to_market_id: str,
    confidence: float,
    edge_type: str = "mutually_exclusive",
) -> DependencyEdge:
    return DependencyEdge(
        edge_id=edge_id,
        edge_type=edge_type,
        from_market_id=from_market_id,
        to_market_id=to_market_id,
        confidence=confidence,
        rationale="fixture rationale",
    )


def test_default_basket_builder_skips_low_confidence_edges_by_default(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.6)]

    baskets, synthetic_edges = DefaultBasketBuilder().build(
        markets,
        dependencies,
        DiscoveryConfig(output_root=tmp_path, embedding_provider="stub"),
    )

    assert baskets == []
    assert synthetic_edges == []


def test_default_basket_builder_honors_confidence_threshold_override(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.92)]
    config = DiscoveryConfig(
        output_root=tmp_path,
        embedding_provider="stub",
        params={
            "basket_builder": {
                "confidence_threshold": 0.95,
            },
        },
    )

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, config)

    assert baskets == []
    assert synthetic_edges == []


def test_default_basket_builder_disables_conservative_gating_when_configured(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.6)]
    config = DiscoveryConfig(
        output_root=tmp_path,
        embedding_provider="stub",
        params={
            "basket_builder": {
                "conservative_gating": False,
                "confidence_threshold": 0.95,
            },
        },
    )

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, config)

    assert len(baskets) == 1
    assert baskets[0].basket_id == "basket-m1__m2"
    assert synthetic_edges == []


@pytest.mark.parametrize(
    "threshold",
    [float("nan"), float("inf"), float("-inf"), -0.1, 1.1],
)
def test_default_basket_builder_rejects_invalid_confidence_threshold(tmp_path: Path, threshold: float) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.95)]
    config = DiscoveryConfig(
        output_root=tmp_path,
        embedding_provider="stub",
        params={
            "basket_builder": {
                "confidence_threshold": threshold,
            },
        },
    )

    with pytest.raises(ValueError, match="confidence_threshold"):
        DefaultBasketBuilder().build(markets, dependencies, config)


def test_default_basket_builder_constructs_deduped_valid_basket(tmp_path: Path) -> None:
    markets = [
        _market("m1", ["tok-shared", "tok-a-yes"]),
        _market("m2", ["tok-shared", "tok-b-yes"]),
    ]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.95)]

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, DiscoveryConfig(output_root=tmp_path, embedding_provider="stub"))

    assert len(baskets) == 1
    basket = baskets[0]
    assert basket.basket_id == "basket-m1__m2"
    assert basket.token_ids == ["tok-shared", "tok-a-yes", "tok-b-yes"]
    assert basket.expected_sum == 1.0
    assert basket.dependency_basis == ["m1__m2"]
    assert synthetic_edges == []


def test_default_basket_builder_skips_related_edges_in_conservative_mode(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.99, edge_type="related")]

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, DiscoveryConfig(output_root=tmp_path, embedding_provider="stub"))

    assert baskets == []
    assert synthetic_edges == []


def test_default_basket_builder_can_build_related_edges_when_conservative_mode_disabled(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"]), _market("m2", ["tok-b-yes"])]
    dependencies = [_edge("m1__m2", "m1", "m2", 0.99, edge_type="related")]
    config = DiscoveryConfig(
        output_root=tmp_path,
        embedding_provider="stub",
        params={
            "basket_builder": {
                "conservative_gating": False,
            },
        },
    )

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, config)

    assert len(baskets) == 1
    assert baskets[0].dependency_basis == ["m1__m2"]
    assert synthetic_edges == []


def test_default_basket_builder_skips_dependencies_with_orphan_market_refs(tmp_path: Path) -> None:
    markets = [_market("m1", ["tok-a-yes"])]
    dependencies = [_edge("m1__missing", "m1", "missing", 0.95)]

    baskets, synthetic_edges = DefaultBasketBuilder().build(markets, dependencies, DiscoveryConfig(output_root=tmp_path, embedding_provider="stub"))

    assert baskets == []
    assert synthetic_edges == []


def test_default_basket_validator_rejects_empty_dependency_basis() -> None:
    basket = BasketItem(
        basket_id="basket-m1__m2",
        token_ids=["tok-a-yes", "tok-b-yes"],
        expected_sum=1.0,
        dependency_basis=[],
    )

    with pytest.raises(ValueError, match="dependency_basis"):
        DefaultBasketValidator().validate([basket])


def test_default_basket_validator_rejects_duplicate_token_ids() -> None:
    basket = BasketItem(
        basket_id="basket-m1__m2",
        token_ids=["tok-a-yes", "tok-a-yes"],
        expected_sum=1.0,
        dependency_basis=["m1__m2"],
    )

    with pytest.raises(ValueError, match="duplicate token ids"):
        DefaultBasketValidator().validate([basket])


def test_default_basket_validator_rejects_non_positive_expected_sum() -> None:
    basket = BasketItem(
        basket_id="basket-m1__m2",
        token_ids=["tok-a-yes", "tok-b-yes"],
        expected_sum=0.0,
        dependency_basis=["m1__m2"],
    )

    with pytest.raises(ValueError, match="expected_sum"):
        DefaultBasketValidator().validate([basket])
