from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.providers.embeddings import HTTPEmbeddingProvider
from polymarket_discovery.providers.embeddings import StubEmbeddingProvider
from polymarket_discovery.providers.factories import build_embedding_provider
from polymarket_discovery.stages import DefaultTopicAssigner


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _MappingEmbeddingProvider:
    def __init__(self, vectors_by_text: dict[str, list[float]], *, fail: bool = False) -> None:
        self._vectors_by_text = vectors_by_text
        self._fail = fail
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._fail:
            raise RuntimeError("embedding provider failed")
        return [self._vectors_by_text[text] for text in texts]


def _market(
    market_id: str,
    *,
    question: str,
    description: str = "",
    rules: str = "",
    topic: str = "",
) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=question,
        description=description,
        rules=rules,
        end_date="2026-11-03",
        topic=topic,
        token_ids=[f"tok-{market_id}"],
    )


def _config(tmp_path: Path, **topic_params: object) -> DiscoveryConfig:
    return DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={"topic_assigner": dict(topic_params)},
    )


def _assigned_topics(markets: list[MarketDescriptor]) -> dict[str, str]:
    return {market.market_id: market.topic for market in markets}


def test_build_embedding_provider_consumes_embedding_model_from_config(tmp_path: Path) -> None:
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="embed-v2",
        llm_model="deepseek-stub-v1",
        params={
            "embedding_model": "embed-v2-params",
            "embedding_dimensions": 12,
        },
    )

    provider = build_embedding_provider(config)

    assert isinstance(provider, StubEmbeddingProvider)
    assert provider.model_name == "embed-v2-params"
    assert provider.dimensions == 12


def test_build_embedding_provider_uses_tei_http_endpoint_with_batching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={
            "embeddings": {
                "embedding_provider": "tei",
                "embedding_model": "linq-embed-mistral",
                "base_url": "http://127.0.0.1:8080/v1/embeddings",
                "timeout_seconds": 4,
                "batch_size": 1,
            },
        },
    )
    seen_requests: list[dict[str, object]] = []

    def fake_urlopen(request, timeout=0):
        seen_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "headers": dict(request.header_items()),
                "body": json.loads(request.data.decode("utf-8")),
            },
        )
        return _FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_embedding_provider(config)
    vectors = provider.embed_texts(["alpha", "beta"])

    assert vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert seen_requests == [
        {
            "url": "http://127.0.0.1:8080/v1/embeddings",
            "timeout": 4,
            "headers": {
                "User-agent": "polymarket-discovery/0.1",
                "Content-type": "application/json",
            },
            "body": {
                "input": ["alpha"],
                "model": "linq-embed-mistral",
            },
        },
        {
            "url": "http://127.0.0.1:8080/v1/embeddings",
            "timeout": 4,
            "headers": {
                "User-agent": "polymarket-discovery/0.1",
                "Content-type": "application/json",
            },
            "body": {
                "input": ["beta"],
                "model": "linq-embed-mistral",
            },
        },
    ]


def test_topic_assigner_merges_embedding_and_topic_tuning_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={
            "embeddings": {
                "embedding_provider": "tei",
                "embedding_model": "linq-embed-mistral",
                "base_url": "http://127.0.0.1:8080/v1/embeddings",
                "timeout_seconds": 4,
                "batch_size": 2,
                "cluster_threshold": 0.95,
                "min_cluster_size": 3,
            },
            "topic_assigner": {
                "embedding_provider": "tei",
                "embedding_model": "topic-assigner-override",
                "embedding_batch_size": 1,
            },
            "topic_clustering": {
                "cluster_threshold": 0.75,
                "min_cluster_size": 2,
            },
        },
    )
    seen_requests: list[dict[str, object]] = []

    def fake_urlopen(request, timeout=0):
        payload = json.loads(request.data.decode("utf-8"))
        text = payload["input"][0]
        seen_requests.append(
            {
                "url": request.full_url,
                "timeout": timeout,
                "body": payload,
            },
        )
        if "Candidate A" in text:
            embedding = [1.0, 0.0, 0.0]
        else:
            embedding = [0.8, 0.6, 0.0]
        return _FakeResponse(
            {
                "data": [{"embedding": embedding}],
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_embedding_provider(config)
    assert isinstance(provider, HTTPEmbeddingProvider)
    assert provider.settings.model_name == "linq-embed-mistral"

    markets = [
        _market("m1", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
        _market("m2", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
    ]

    assigned = DefaultTopicAssigner(embedding_provider=provider).assign_topics(markets, config)

    assert len(seen_requests) == 2
    assert [request["body"]["input"] for request in seen_requests] == [
        ["Will Candidate A win?\nElection market\nStandard rules"],
        ["Will Candidate A win?\nElection market\nStandard rules"],
    ]
    assert assigned[0].topic == assigned[1].topic == "topic-01"


def test_build_embedding_provider_retries_transient_transport_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={
            "embeddings": {
                "embedding_provider": "tei",
                "embedding_model": "linq-embed-mistral",
                "base_url": "http://127.0.0.1:8080/v1/embeddings",
                "timeout_seconds": 4,
                "batch_size": 2,
                "retry": {"max_attempts": 2, "backoff_seconds": 0.0, "backoff_factor": 1.0},
            },
        },
    )
    calls = {"count": 0}

    def fake_urlopen(request, timeout=0):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("temporary failure")
        return _FakeResponse({"data": [{"embedding": [0.4, 0.5, 0.6]}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_embedding_provider(config)
    vectors = provider.embed_texts(["alpha"])

    assert vectors == [[0.4, 0.5, 0.6]]
    assert calls["count"] == 2


def test_build_embedding_provider_rejects_bad_payload_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={
            "embeddings": {
                "embedding_provider": "tei",
                "embedding_model": "linq-embed-mistral",
                "base_url": "http://127.0.0.1:8080/v1/embeddings",
                "timeout_seconds": 4,
                "batch_size": 2,
                "retry": {"max_attempts": 3, "backoff_seconds": 0.0, "backoff_factor": 1.0},
            },
        },
    )
    calls = {"count": 0}

    def fake_urlopen(request, timeout=0):
        calls["count"] += 1
        return _FakeResponse({"data": [{}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_embedding_provider(config)

    with pytest.raises(ValueError, match="embedding vectors"):
        provider.embed_texts(["alpha"])

    assert calls["count"] == 1


def test_embedding_topic_assigner_clusters_by_embedding_text_and_batches(tmp_path: Path) -> None:
    markets = [
        _market("m1", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
        _market("m2", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
        _market("m3", question="Will the Fed cut rates?", description="Macro market", rules="Standard rules"),
        _market("m4", question="Will the Fed cut rates?", description="Macro market", rules="Standard rules"),
        _market("m5", question="Will the exhibit sell out?", description="Event market", rules="Standard rules", topic="event"),
    ]
    vectors_by_text = {
        "Will Candidate A win?\nElection market\nStandard rules": [1.0, 0.0, 0.0],
        "Will the Fed cut rates?\nMacro market\nStandard rules": [0.0, 1.0, 0.0],
        "Will the exhibit sell out?\nEvent market\nStandard rules": [0.0, 0.0, 1.0],
    }
    provider = _MappingEmbeddingProvider(vectors_by_text)
    config = _config(
        tmp_path,
        embedding_batch_size=2,
        cluster_threshold=0.9,
        min_cluster_size=2,
    )

    assigned = DefaultTopicAssigner(embedding_provider=provider).assign_topics(markets, config)
    topics = _assigned_topics(assigned)

    assert provider.calls == [
        [
            "Will Candidate A win?\nElection market\nStandard rules",
            "Will Candidate A win?\nElection market\nStandard rules",
        ],
        [
            "Will the Fed cut rates?\nMacro market\nStandard rules",
            "Will the Fed cut rates?\nMacro market\nStandard rules",
        ],
        [
            "Will the exhibit sell out?\nEvent market\nStandard rules",
        ],
    ]
    assert topics["m1"] == topics["m2"]
    assert topics["m3"] == topics["m4"]
    assert topics["m1"] != topics["m3"]
    assert topics["m5"] == "event"
    assert topics["m1"].startswith("topic-")
    assert topics["m3"].startswith("topic-")


def test_embedding_topic_labels_are_stable_for_the_same_cluster_set(tmp_path: Path) -> None:
    markets = [
        _market("m1", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
        _market("m2", question="Will Candidate A win?", description="Election market", rules="Standard rules"),
        _market("m3", question="Will the Fed cut rates?", description="Macro market", rules="Standard rules"),
        _market("m4", question="Will the Fed cut rates?", description="Macro market", rules="Standard rules"),
    ]
    provider_a = _MappingEmbeddingProvider(
        {
            "Will Candidate A win?\nElection market\nStandard rules": [1.0, 0.0],
            "Will the Fed cut rates?\nMacro market\nStandard rules": [0.0, 1.0],
        },
    )
    provider_b = _MappingEmbeddingProvider(
        {
            "Will Candidate A win?\nElection market\nStandard rules": [1.0, 0.0],
            "Will the Fed cut rates?\nMacro market\nStandard rules": [0.0, 1.0],
        },
    )
    config = _config(
        tmp_path,
        embedding_batch_size=3,
        cluster_threshold=0.9,
        min_cluster_size=2,
    )

    assigned_a = DefaultTopicAssigner(embedding_provider=provider_a).assign_topics(markets, config)
    assigned_b = DefaultTopicAssigner(embedding_provider=provider_b).assign_topics(list(reversed(markets)), config)

    assert _assigned_topics(assigned_a) == _assigned_topics(assigned_b)
    assert _assigned_topics(assigned_a)["m1"] == "topic-01"
    assert _assigned_topics(assigned_a)["m3"] == "topic-02"


def test_embedding_topic_assigner_falls_back_when_provider_raises(tmp_path: Path) -> None:
    markets = [
        _market("m1", question="Will Candidate A win?"),
        _market("m2", question="Will Candidate B win?", topic="politics"),
    ]
    provider = _MappingEmbeddingProvider({}, fail=True)
    config = _config(
        tmp_path,
        embedding_batch_size=4,
        cluster_threshold=0.9,
        min_cluster_size=2,
    )

    assigned = DefaultTopicAssigner(embedding_provider=provider).assign_topics(markets, config)

    assert _assigned_topics(assigned) == {
        "m1": "unassigned",
        "m2": "politics",
    }


def test_embedding_topic_assigner_raises_on_invalid_batch_size(tmp_path: Path) -> None:
    markets = [_market("m1", question="Will Candidate A win?")]
    provider = _MappingEmbeddingProvider(
        {
            "Will Candidate A win?": [1.0, 0.0],
        },
    )
    config = _config(
        tmp_path,
        embedding_batch_size=0,
        cluster_threshold=0.9,
        min_cluster_size=2,
    )

    with pytest.raises(ValueError, match="embedding_batch_size must be greater than zero"):
        DefaultTopicAssigner(embedding_provider=provider).assign_topics(markets, config)

    assert provider.calls == []


def test_embedding_topic_assigner_raises_for_unsupported_provider(tmp_path: Path) -> None:
    markets = [_market("m1", question="Will Candidate A win?")]
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="unsupported-provider",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-stub-v1",
        params={
            "topic_assigner": {
                "embedding_batch_size": 1,
                "cluster_threshold": 0.9,
                "min_cluster_size": 2,
            },
        },
    )

    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        DefaultTopicAssigner().assign_topics(markets, config)
