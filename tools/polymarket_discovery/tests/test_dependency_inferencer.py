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
from polymarket_discovery.providers.llm_codec import parse_llm_dependency_prediction
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
    def __init__(self, prediction: LLMDependencyPrediction) -> None:
        self._prediction = prediction
        self.calls: list[tuple[str, str]] = []

    def infer_dependency(self, left_market: MarketDescriptor, right_market: MarketDescriptor) -> LLMDependencyPrediction:
        self.calls.append((left_market.market_id, right_market.market_id))
        return self._prediction


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
                            "content": '{"edge_type":"mutually_exclusive","confidence":0.97,"rationale":"Only one winner can resolve true."}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = build_llm_provider(config)
    prediction = provider.infer_dependency(_market("m1", "Will Candidate A win?"), _market("m2", "Will Candidate B win?"))

    assert prediction.edge_type == "mutually_exclusive"
    assert prediction.confidence == pytest.approx(0.97)
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
                            "content": '{"edge_type":"related","confidence":0.4,"rationale":"Shared event."}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_llm_provider(config)
    prediction = provider.infer_dependency(_market("m1", "Left?"), _market("m2", "Right?"))

    assert prediction.edge_type == "related"
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
                            "content": '{"edge_type":"related","confidence":0.61,"rationale":"Local vLLM response."}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = build_llm_provider(config)
    prediction = provider.infer_dependency(_market("m1", "Left?"), _market("m2", "Right?"))

    assert prediction.edge_type == "related"
    assert prediction.confidence == pytest.approx(0.61)
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
                            "content": '{"edge_type":"related","confidence":0.5,"rationale":"Same election context."}'
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
                            "content": '{"edge_type":"conditional","confidence":0.55,"rationale":"Resolution dependency."}'
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
    inferencer = LLMDependencyInferencer(_StaticProvider(prediction))

    with pytest.raises(ValueError, match=expected_message):
        inferencer.infer_dependencies([(_market("m1", "Left?"), _market("m2", "Right?"))])
