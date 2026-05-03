from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.interfaces.llm_dependency_prediction import LLMDependencyPrediction
from polymarket_discovery.providers.factories import build_llm_provider
from polymarket_discovery.providers.llm_codec import (
    DEFAULT_DEPENDENCY_BATCH_SIZE,
    parse_llm_dependency_prediction,
    build_batched_dependency_prompt,
    parse_batched_dependency_predictions,
    validate_batched_dependency_predictions,
)
from polymarket_discovery.providers.llm_stub import DeepSeekLLMProviderStub
from polymarket_discovery.stages import LLMDependencyInferencer


@dataclass
class _FakeResponse:
    payload: object

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _StaticProvider:
    """Test double that returns a fixed prediction for every pair in a batch."""

    def __init__(self, prediction: LLMDependencyPrediction) -> None:
        self._prediction = prediction
        self.batch_calls: list[list[tuple[str, str]]] = []

    def infer_dependencies_batched(
        self,
        pairs: object,
    ) -> list[LLMDependencyPrediction]:
        pair_ids = [(left.market_id, right.market_id) for left, right in pairs]  # type: ignore[union-attr]
        self.batch_calls.append(pair_ids)
        return [self._prediction for _ in pairs]  # type: ignore[arg-type]


def _market(market_id: str, question: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=question,
        description="desc",
        end_date="2026-11-03",
        topic="election",
        token_ids=[f"tok-{market_id}"],
    )


def _config(tmp_path: Path, **params: object) -> DiscoveryConfig:
    return DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="fixture",
        embedding_provider="stub",
        embedding_model="stub-embed-v1",
        llm_model="deepseek-chat",
        params=dict(params),
    )


def test_parse_llm_dependency_prediction_accepts_valid_json_object() -> None:
    prediction = parse_llm_dependency_prediction(
        '{"edge_type":"conditional","confidence":0.42,"rationale":"Shared resolution condition."}'
    )

    assert prediction == LLMDependencyPrediction(
        edge_type="conditional",
        confidence=0.42,
        rationale="Shared resolution condition.",
    )


@pytest.mark.parametrize(
    "raw_response, expected_message",
    [
        ('{"edge_type":"basket","confidence":0.4,"rationale":"bad"}', "edge_type"),
        ('{"edge_type":"related","confidence":1.2,"rationale":"bad"}', "confidence"),
        ('{"edge_type":"related","confidence":-0.1,"rationale":"bad"}', "confidence"),
        ('{"edge_type":"related","confidence":"high","rationale":"bad"}', "confidence"),
        ('{"edge_type":"related","confidence":0.1}', "rationale"),
        ('[]', "JSON object"),
        ('not-json', "valid JSON"),
    ],
)
def test_parse_llm_dependency_prediction_rejects_invalid_payloads(raw_response: str, expected_message: str) -> None:
    with pytest.raises(ValueError, match=expected_message):
        parse_llm_dependency_prediction(raw_response)


def test_build_llm_provider_returns_stub_by_default(tmp_path: Path) -> None:
    provider = build_llm_provider(_config(tmp_path))

    assert isinstance(provider, DeepSeekLLMProviderStub)
    assert provider.model_name == "deepseek-chat"


def test_build_llm_provider_uses_configured_real_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(
        tmp_path,
        llm_provider="deepseek",
        dependency_inferencer={
            "temperature": 0.15,
            "max_tokens": 128,
            "retry": {"max_attempts": 2, "backoff_seconds": 0.0, "backoff_factor": 1.0},
            "api_key": "test-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
            "timeout_seconds": 3,
        },
    )
    seen_request: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        seen_request["url"] = request.full_url
        seen_request["timeout"] = timeout
        seen_request["headers"] = dict(request.header_items())
        seen_request["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"predictions":[{"pair_id":"0","edge_type":"mutually_exclusive","confidence":0.97,"rationale":"Only one winner can resolve true."}]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = build_llm_provider(config)
    predictions = provider.infer_dependencies_batched([(_market("m1", "Will Candidate A win?"), _market("m2", "Will Candidate B win?"))])

    assert len(predictions) == 1
    assert predictions[0].edge_type == "mutually_exclusive"
    assert predictions[0].confidence == pytest.approx(0.97)
    assert seen_request["url"] == "https://api.deepseek.com/chat/completions"
    assert seen_request["timeout"] == 3
    assert seen_request["headers"]["Authorization"] == "Bearer test-secret"
    assert seen_request["body"]["model"] == "deepseek-chat"
    assert seen_request["body"]["temperature"] == pytest.approx(0.15)
    assert seen_request["body"]["max_tokens"] == 128
    assert seen_request["body"]["response_format"] == {"type": "json_object"}


def test_build_llm_provider_inferrs_real_provider_from_api_settings_without_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "api_key": "test-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
            "temperature": 0.0,
            "max_tokens": 64,
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )
    seen_request: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        seen_request["url"] = request.full_url
        seen_request["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"predictions":[{"pair_id":"0","edge_type":"related","confidence":0.4,"rationale":"Shared event."}]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_llm_provider(config)
    predictions = provider.infer_dependencies_batched([(_market("m1", "Left?"), _market("m2", "Right?"))])

    assert len(predictions) == 1
    assert predictions[0].edge_type == "related"
    assert seen_request["url"] == "https://api.deepseek.com/chat/completions"


def test_build_llm_provider_honors_explicit_stub_override_even_with_api_settings(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        llm_provider="stub",
        dependency_inferencer={
            "api_key": "test-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
        },
    )

    provider = build_llm_provider(config)

    assert isinstance(provider, DeepSeekLLMProviderStub)


def test_build_llm_provider_uses_vllm_openai_alias_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "provider_name": "vllm_openai",
            "base_url": "http://127.0.0.1:8000/v1/chat/completions",
            "model": "glm-4-9b",
            "temperature": 0.1,
            "max_tokens": 96,
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )
    seen_request: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        seen_request["url"] = request.full_url
        seen_request["timeout"] = timeout
        seen_request["headers"] = dict(request.header_items())
        seen_request["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"predictions":[{"pair_id":"0","edge_type":"related","confidence":0.61,"rationale":"Local vLLM response."}]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_llm_provider(config)
    predictions = provider.infer_dependencies_batched([(_market("m1", "Left?"), _market("m2", "Right?"))])

    assert len(predictions) == 1
    assert predictions[0].edge_type == "related"
    assert predictions[0].confidence == pytest.approx(0.61)
    assert seen_request["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert seen_request["headers"]["Content-type"] == "application/json"
    assert "Authorization" not in seen_request["headers"]
    assert seen_request["body"]["model"] == "glm-4-9b"
    assert seen_request["body"]["max_tokens"] == 96


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:8000/v1/chat/completions",
        "http://[::1]:8000/v1/chat/completions",
    ],
)
def test_build_llm_provider_allows_only_loopback_endpoints_without_api_key(
    tmp_path: Path,
    base_url: str,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "provider_name": "vllm_openai",
            "base_url": base_url,
            "model": "glm-4-9b",
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )

    provider = build_llm_provider(config)

    assert provider is not None


def test_build_llm_provider_rejects_private_endpoints_without_api_key(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "provider_name": "vllm_openai",
            "base_url": "http://192.168.1.10:8000/v1/chat/completions",
            "model": "glm-4-9b",
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )

    with pytest.raises(ValueError, match="api_key is required"):
        build_llm_provider(config)


def test_llm_dependency_inferencer_builds_provider_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(
        tmp_path,
        llm_provider="deepseek",
        dependency_inferencer={
            "api_key": "test-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
            "temperature": 0,
            "max_tokens": 64,
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )

    def fake_urlopen(request, timeout=0):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"predictions":[{"pair_id":"0","edge_type":"related","confidence":0.5,"rationale":"Same election context."}]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    inferencer = LLMDependencyInferencer()

    edges = inferencer.infer_dependencies([(_market("m1", "Will Candidate A win?"), _market("m2", "Will Candidate B win?"))], config)

    assert len(edges) == 1
    assert edges[0].edge_type == "related"
    assert edges[0].confidence == pytest.approx(0.5)


def test_llm_dependency_inferencer_prefers_real_provider_when_api_settings_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(
        tmp_path,
        dependency_inferencer={
            "api_key": "test-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
            "temperature": 0,
            "max_tokens": 64,
            "retry": {"max_attempts": 1, "backoff_seconds": 0.0, "backoff_factor": 1.0},
        },
    )

    def fake_urlopen(request, timeout=0):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"predictions":[{"pair_id":"0","edge_type":"conditional","confidence":0.55,"rationale":"Resolution dependency."}]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    inferencer = LLMDependencyInferencer(
        _StaticProvider(
            LLMDependencyPrediction(
                edge_type="related",
                confidence=0.2,
                rationale="stub path should not win",
            )
        )
    )

    edges = inferencer.infer_dependencies([(_market("m1", "Left?"), _market("m2", "Right?"))], config)

    assert len(edges) == 1
    assert edges[0].edge_type == "conditional"
    assert edges[0].confidence == pytest.approx(0.55)


class _InvalidBatchProvider:
    """Test double that returns a fixed (possibly invalid) prediction for every pair."""

    def __init__(self, prediction: LLMDependencyPrediction) -> None:
        self._prediction = prediction

    def infer_dependencies_batched(
        self,
        pairs: object,
    ) -> list[LLMDependencyPrediction]:
        return [self._prediction for _ in pairs]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "prediction, expected_message",
    [
        (LLMDependencyPrediction(edge_type="basket", confidence=0.4, rationale="bad"), "edge_type"),
        (LLMDependencyPrediction(edge_type="related", confidence=1.1, rationale="bad"), "confidence"),
        (LLMDependencyPrediction(edge_type="related", confidence=-0.1, rationale="bad"), "confidence"),
    ],
)
def test_llm_dependency_inferencer_rejects_invalid_provider_predictions(
    prediction: LLMDependencyPrediction,
    expected_message: str,
) -> None:
    # The inferencer must validate predictions returned by the provider;
    # invalid predictions must raise ValueError even when wrapped in a batch.
    inferencer = LLMDependencyInferencer(_InvalidBatchProvider(prediction))

    with pytest.raises(ValueError, match=expected_message):
        inferencer.infer_dependencies([(_market("m1", "Left?"), _market("m2", "Right?"))])


# ---------------------------------------------------------------------------
# Batched inference tests
# ---------------------------------------------------------------------------


class _CountingProvider:
    """Test double that records each call to infer_dependencies_batched.

    Lets tests assert that N pairs produce exactly ceil(N / batch_size) calls,
    not N calls.
    """

    def __init__(self) -> None:
        self.call_count: int = 0
        self.received_chunks: list[list[tuple[str, str]]] = []

    def infer_dependencies_batched(
        self,
        pairs: object,
    ) -> list[LLMDependencyPrediction]:
        pair_list = list(pairs)  # type: ignore[arg-type]
        self.call_count += 1
        self.received_chunks.append([(l.market_id, r.market_id) for l, r in pair_list])
        return [
            LLMDependencyPrediction(
                edge_type="related",
                confidence=0.6,
                rationale="stub",
            )
            for _ in pair_list
        ]


def test_batched_inferencer_calls_provider_once_for_n_pairs_within_chunk() -> None:
    """N pairs that fit in one chunk must produce exactly ONE provider call."""
    provider = _CountingProvider()
    inferencer = LLMDependencyInferencer(provider)

    markets = [_market(f"m{i}", f"Q{i}?") for i in range(5)]
    pairs = [(markets[i], markets[j]) for i in range(len(markets)) for j in range(i + 1, len(markets))]
    # 5 markets → 10 pairs, well within the default batch_size of 50

    edges = inferencer.infer_dependencies(pairs)

    assert provider.call_count == 1, (
        f"Expected 1 batched call for {len(pairs)} pairs, got {provider.call_count}"
    )
    assert len(edges) == len(pairs)


def test_batched_inferencer_chunks_large_pair_lists(tmp_path: Path) -> None:
    """Pairs exceeding batch_size must be split into ceil(N/batch_size) calls."""
    provider = _CountingProvider()
    inferencer = LLMDependencyInferencer(provider)

    # Use a small batch_size so we exercise chunking without needing a huge pair list.
    config = _config(tmp_path, dependency_inferencer={"batch_size": 3})
    pairs = [(_market(f"m{i}", f"Q{i}?"), _market(f"m{i+1}", f"Q{i+1}?")) for i in range(7)]
    # 7 pairs with batch_size=3 → ceil(7/3) = 3 calls

    edges = inferencer.infer_dependencies(pairs, config)

    assert provider.call_count == 3, (
        f"Expected 3 batched calls for 7 pairs at batch_size=3, got {provider.call_count}"
    )
    assert len(edges) == 7


def test_batched_inferencer_chunk_sizes_are_correct(tmp_path: Path) -> None:
    """Each chunk must contain at most batch_size pairs; last chunk is the remainder."""
    provider = _CountingProvider()
    inferencer = LLMDependencyInferencer(provider)

    config = _config(tmp_path, dependency_inferencer={"batch_size": 3})
    pairs = [(_market(f"m{i}", f"Q{i}?"), _market(f"m{i+1}", f"Q{i+1}?")) for i in range(7)]

    inferencer.infer_dependencies(pairs, config)

    chunk_sizes = [len(chunk) for chunk in provider.received_chunks]
    assert chunk_sizes == [3, 3, 1], f"Unexpected chunk sizes: {chunk_sizes}"


def test_batched_inferencer_preserves_edge_order(tmp_path: Path) -> None:
    """Edge order must match input pair order even when chunked."""
    provider = _CountingProvider()
    inferencer = LLMDependencyInferencer(provider)

    config = _config(tmp_path, dependency_inferencer={"batch_size": 2})
    pairs = [(_market(f"a{i}", f"Left{i}?"), _market(f"b{i}", f"Right{i}?")) for i in range(5)]

    edges = inferencer.infer_dependencies(pairs, config)

    for i, ((left, right), edge) in enumerate(zip(pairs, edges)):
        assert edge.from_market_id == left.market_id, f"pair {i}: wrong from_market_id"
        assert edge.to_market_id == right.market_id, f"pair {i}: wrong to_market_id"
        assert edge.edge_id == f"{left.market_id}__{right.market_id}"


def test_batched_inferencer_returns_empty_for_no_pairs() -> None:
    """Zero pairs must return an empty list without calling the provider."""
    provider = _CountingProvider()
    inferencer = LLMDependencyInferencer(provider)

    edges = inferencer.infer_dependencies([])

    assert edges == []
    assert provider.call_count == 0


def test_default_dependency_batch_size_constant() -> None:
    """DEFAULT_DEPENDENCY_BATCH_SIZE must be a positive integer exported by llm_codec."""
    assert isinstance(DEFAULT_DEPENDENCY_BATCH_SIZE, int)
    assert DEFAULT_DEPENDENCY_BATCH_SIZE > 0


def test_stub_provider_produces_valid_batched_responses() -> None:
    """DeepSeekLLMProviderStub.infer_dependencies_batched must return one validated result per pair."""
    stub = DeepSeekLLMProviderStub(model_name="test-stub")
    markets = [_market(f"m{i}", f"Q{i}?") for i in range(4)]
    pairs = [(markets[0], markets[1]), (markets[1], markets[2]), (markets[2], markets[3])]

    results = stub.infer_dependencies_batched(pairs)

    assert len(results) == len(pairs)
    for result in results:
        assert result.edge_type in {"mutually_exclusive", "conditional", "related"}
        assert 0.0 <= result.confidence <= 1.0
        assert result.rationale


def test_stub_provider_uses_lexical_heuristic_in_batch() -> None:
    """Stub must return mutually_exclusive when lexical heuristic matches in a batch."""
    stub = DeepSeekLLMProviderStub(model_name="test-stub")
    yes_market = _market("m1", "Will candidate A win? Yes")
    no_market = _market("m2", "Will candidate A win? No")
    unrelated = _market("m3", "What is the GDP growth?")

    results = stub.infer_dependencies_batched([
        (yes_market, no_market),    # should be mutually_exclusive
        (yes_market, unrelated),    # should be related
    ])

    assert results[0].edge_type == "mutually_exclusive"
    assert results[1].edge_type == "related"


# ---------------------------------------------------------------------------
# Codec-level batched tests
# ---------------------------------------------------------------------------


def test_build_batched_dependency_prompt_assigns_sequential_pair_ids() -> None:
    """build_batched_dependency_prompt must assign pair_id '0', '1', ... in order."""
    markets = [_market(f"m{i}", f"Q{i}?") for i in range(3)]
    pairs = [(markets[0], markets[1]), (markets[1], markets[2])]

    prompt_str = build_batched_dependency_prompt(pairs)
    payload = json.loads(prompt_str)

    assert "pairs" in payload
    assert len(payload["pairs"]) == 2
    assert payload["pairs"][0]["pair_id"] == "0"
    assert payload["pairs"][1]["pair_id"] == "1"
    assert payload["pairs"][0]["left_market"]["market_id"] == "m0"
    assert payload["pairs"][0]["right_market"]["market_id"] == "m1"


def test_parse_batched_dependency_predictions_round_trips_all_pair_ids() -> None:
    """parse_batched_dependency_predictions must return results in pair_id index order."""
    # LLM returns pair_id=1 before pair_id=0 (reordered response).
    raw = json.dumps({
        "predictions": [
            {"pair_id": "1", "edge_type": "related", "confidence": 0.4, "rationale": "second"},
            {"pair_id": "0", "edge_type": "conditional", "confidence": 0.8, "rationale": "first"},
        ]
    })

    results = parse_batched_dependency_predictions(raw, expected_count=2)

    assert len(results) == 2
    assert results[0].edge_type == "conditional"   # pair_id=0
    assert results[0].rationale == "first"
    assert results[1].edge_type == "related"        # pair_id=1
    assert results[1].rationale == "second"


def test_parse_batched_dependency_predictions_raises_on_missing_pair_id() -> None:
    """Missing pair_id in response must raise ValueError with a clear message."""
    raw = json.dumps({
        "predictions": [
            {"pair_id": "0", "edge_type": "related", "confidence": 0.5, "rationale": "ok"},
            # pair_id "1" is absent
        ]
    })

    with pytest.raises(ValueError, match="missing"):
        parse_batched_dependency_predictions(raw, expected_count=2)


def test_parse_batched_dependency_predictions_raises_on_unexpected_pair_id() -> None:
    """An unexpected pair_id in the response must raise ValueError."""
    raw = json.dumps({
        "predictions": [
            {"pair_id": "99", "edge_type": "related", "confidence": 0.5, "rationale": "rogue"},
        ]
    })

    with pytest.raises(ValueError, match="unexpected"):
        parse_batched_dependency_predictions(raw, expected_count=1)


def test_parse_batched_dependency_predictions_raises_on_duplicate_pair_id() -> None:
    """Duplicate pair_id in a response must raise ValueError."""
    raw = json.dumps({
        "predictions": [
            {"pair_id": "0", "edge_type": "related", "confidence": 0.5, "rationale": "first"},
            {"pair_id": "0", "edge_type": "conditional", "confidence": 0.8, "rationale": "dup"},
        ]
    })

    with pytest.raises(ValueError, match="duplicate"):
        parse_batched_dependency_predictions(raw, expected_count=2)


def test_parse_batched_dependency_predictions_raises_on_invalid_edge_type() -> None:
    """Each prediction in the batch must pass individual validation (edge_type)."""
    raw = json.dumps({
        "predictions": [
            {"pair_id": "0", "edge_type": "basket", "confidence": 0.5, "rationale": "bad"},
        ]
    })

    with pytest.raises(ValueError, match="edge_type"):
        parse_batched_dependency_predictions(raw, expected_count=1)


def test_parse_batched_dependency_predictions_raises_on_non_predictions_array() -> None:
    """Response without a 'predictions' array must raise ValueError."""
    raw = json.dumps({"edge_type": "related", "confidence": 0.5, "rationale": "wrong shape"})

    with pytest.raises(ValueError, match="predictions"):
        parse_batched_dependency_predictions(raw, expected_count=1)


def test_parse_batched_dependency_predictions_integer_pair_id_is_accepted() -> None:
    """pair_id supplied as an integer (not a string) must be accepted and coerced."""
    raw = json.dumps({
        "predictions": [
            {"pair_id": 0, "edge_type": "related", "confidence": 0.5, "rationale": "coerced"},
        ]
    })

    results = parse_batched_dependency_predictions(raw, expected_count=1)

    assert len(results) == 1
    assert results[0].edge_type == "related"
