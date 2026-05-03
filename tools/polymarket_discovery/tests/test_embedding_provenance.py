"""Tests proving that the pipeline fails loudly when no embedding provider is
configured, that explicit opt-in to the stub works, and that run artifacts
record embedding provenance accurately.
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

from polymarket_discovery.config import DiscoveryConfig, load_config
from polymarket_discovery.contracts import MarketDescriptor
from polymarket_discovery.providers.embeddings import StubEmbeddingProvider
from polymarket_discovery.providers.factories import build_embedding_provider
from polymarket_discovery.providers.settings import resolve_embedding_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market(market_id: str) -> MarketDescriptor:
    return MarketDescriptor(
        market_id=market_id,
        condition_id=f"cond-{market_id}",
        question=f"Question {market_id}",
        description="Description",
        end_date="2026-11-03",
        topic="topic-01",
        token_ids=[f"tok-{market_id}"],
    )


# ---------------------------------------------------------------------------
# 1. Fail-loud: no config at all must raise
# ---------------------------------------------------------------------------

def test_build_embedding_provider_raises_when_called_with_no_config() -> None:
    """build_embedding_provider(None) must not silently return a stub provider."""
    with pytest.raises(ValueError, match="No embedding provider configured"):
        build_embedding_provider(None)


def test_build_embedding_provider_raises_when_config_has_no_embedding_provider(
    tmp_path: Path,
) -> None:
    """A DiscoveryConfig whose embedding_provider field was somehow cleared to an
    empty string must also fail loudly.  (The normal DiscoveryConfig default is
    'stub', which is the explicit opt-in — this tests a deliberately broken config.)
    """
    # Construct a settings dict that resolves to empty provider_name.
    # We achieve this by bypassing DiscoveryConfig and passing a config-like
    # object with an empty embedding_provider attribute.
    class _EmptyProviderConfig:
        params: dict = {}
        embedding_provider: str = ""
        embedding_model: str = "some-model"

    with pytest.raises(ValueError, match="No embedding provider configured"):
        build_embedding_provider(_EmptyProviderConfig())


# ---------------------------------------------------------------------------
# 2. Explicit stub opt-in must work
# ---------------------------------------------------------------------------

def test_build_embedding_provider_explicit_stub_opt_in(tmp_path: Path) -> None:
    """Explicitly setting embedding_provider='stub' must return StubEmbeddingProvider."""
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        embedding_provider="stub",
        embedding_model="stub-embed",
    )
    provider = build_embedding_provider(config)
    assert isinstance(provider, StubEmbeddingProvider)


def test_build_embedding_provider_explicit_stub_aliases(tmp_path: Path) -> None:
    """All documented stub aliases (deterministic, hash) must work."""
    for alias in ("deterministic", "hash"):
        config = DiscoveryConfig(
            output_root=tmp_path / "artifacts",
            embedding_provider=alias,
            embedding_model="stub-embed",
        )
        provider = build_embedding_provider(config)
        assert isinstance(provider, StubEmbeddingProvider), f"alias '{alias}' did not return StubEmbeddingProvider"


def test_build_embedding_provider_stub_in_params_overrides_top_level(tmp_path: Path) -> None:
    """embedding_provider set inside params.embeddings also activates the stub."""
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        embedding_provider="stub",  # top-level opt-in
        embedding_model="stub-embed",
        params={
            "embeddings": {
                "embedding_provider": "stub",
                "embedding_model": "params-stub-embed",
                "embedding_dimensions": 4,
            },
        },
    )
    provider = build_embedding_provider(config)
    assert isinstance(provider, StubEmbeddingProvider)
    assert provider.dimensions == 4


# ---------------------------------------------------------------------------
# 3. Misconfigured HTTP provider must fail loudly (not fall back to stub)
# ---------------------------------------------------------------------------

def test_build_embedding_provider_raises_when_base_url_missing_for_http_provider(
    tmp_path: Path,
) -> None:
    """Specifying a real provider name like 'tei' but omitting base_url must raise,
    not silently fall back to the stub.
    """
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        embedding_provider="tei",
        embedding_model="linq-embed-mistral",
        params={
            "embeddings": {
                "embedding_provider": "tei",
                # base_url intentionally omitted
            },
        },
    )
    with pytest.raises(ValueError, match="base_url is required"):
        build_embedding_provider(config)


def test_resolve_embedding_settings_returns_empty_provider_name_when_unconfigured() -> None:
    """resolve_embedding_settings(None) must return empty provider_name, not 'stub',
    so the factory can detect the unconfigured state.
    """
    settings = resolve_embedding_settings(None)
    assert settings.provider_name == "", (
        f"Expected empty provider_name for unconfigured settings, got '{settings.provider_name}'"
    )


# ---------------------------------------------------------------------------
# 4. Artifact provenance: embedding_provider field must be recorded accurately
# ---------------------------------------------------------------------------

def test_run_artifact_records_stub_embedding_provider(tmp_path: Path) -> None:
    """A full pipeline run with stub embeddings must record 'stub' in
    run_metadata.embedding_provider of the output artifact.
    """
    from polymarket_discovery.cli import run_command

    config_payload = {
        "output_root": str(tmp_path / "artifacts"),
        "artifact_subdir": "runs",
        "market_source": "fixture",
        "embedding_provider": "stub",
        "embedding_model": "stub-embed-v1",
        "llm_model": "deepseek-stub-v1",
        "params": {
            "markets": [
                {
                    "market_id": "p1",
                    "condition_id": "cond-p1",
                    "question": "Will A win?",
                    "description": "Test",
                    "end_date": "2026-11-03",
                    "topic": "election",
                    "token_ids": ["tok-p1-yes", "tok-p1-no"],
                },
                {
                    "market_id": "p2",
                    "condition_id": "cond-p2",
                    "question": "Will B win?",
                    "description": "Test",
                    "end_date": "2026-11-03",
                    "topic": "election",
                    "token_ids": ["tok-p2-yes", "tok-p2-no"],
                },
            ],
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")

    exit_code = run_command(config_path)
    assert exit_code == 0

    run_root = tmp_path / "artifacts" / "runs"
    run_dirs = sorted(p for p in run_root.iterdir() if p.is_dir())
    assert len(run_dirs) == 1

    payload = json.loads((run_dirs[0] / "baskets.json").read_text(encoding="utf-8"))
    assert payload["run_metadata"]["embedding_provider"] == "stub", (
        "Artifact must record embedding_provider='stub' for stub runs so Phase 2 "
        "consumers can filter them out."
    )


def test_run_metadata_embedding_provider_field_matches_config(tmp_path: Path) -> None:
    """run_metadata.embedding_provider must reflect whatever provider was configured,
    ensuring downstream consumers can distinguish stub from real runs.
    """
    from polymarket_discovery.contracts import RunMetadata

    # stub run
    meta_stub = RunMetadata(
        run_id="run-stub",
        generated_at_utc="2026-05-01T00:00:00Z",
        market_source="fixture",
        embedding_model="stub-embed",
        llm_model="stub-llm",
        embedding_provider="stub",
    )
    assert meta_stub.embedding_provider == "stub"

    # real HTTP provider run
    meta_real = RunMetadata(
        run_id="run-real",
        generated_at_utc="2026-05-01T00:00:00Z",
        market_source="polymarket-api",
        embedding_model="linq-embed-mistral",
        llm_model="deepseek-v3",
        embedding_provider="tei",
    )
    assert meta_real.embedding_provider == "tei"


def test_schema_accepts_run_metadata_with_embedding_provider() -> None:
    """The output schema must accept the embedding_provider field on run_metadata."""
    from polymarket_discovery.serialization import validate_output_document

    payload = {
        "schema_version": "v1",
        "run_metadata": {
            "run_id": "run_20260501T000000Z_00000000000e",
            "generated_at_utc": "2026-05-01T00:00:00Z",
            "market_source": "fixture",
            "embedding_model": "stub-embed-v1",
            "llm_model": "deepseek-stub-v1",
            "embedding_provider": "stub",
            "schema_version": "v1",
        },
        "markets": [
            {
                "market_id": "m1",
                "condition_id": "cond-m1",
                "question": "Will A win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-m1-yes", "tok-m1-no"],
            },
            {
                "market_id": "m2",
                "condition_id": "cond-m2",
                "question": "Will B win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-m2-yes", "tok-m2-no"],
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
            }
        ],
        "baskets": [
            {
                "basket_id": "basket-m1__m2",
                "token_ids": ["tok-m1-yes", "tok-m1-no", "tok-m2-yes", "tok-m2-no"],
                "expected_sum": 1.0,
                "dependency_basis": ["m1__m2"],
            }
        ],
    }
    # Must not raise
    validate_output_document(payload)


def test_schema_still_accepts_run_metadata_without_embedding_provider() -> None:
    """Existing artifacts without embedding_provider must remain valid (backward compat)."""
    from polymarket_discovery.serialization import validate_output_document

    payload = {
        "schema_version": "v1",
        "run_metadata": {
            "run_id": "run_20260501T000000Z_00000000000e",
            "generated_at_utc": "2026-05-01T00:00:00Z",
            "market_source": "fixture",
            "embedding_model": "stub-embed-v1",
            "llm_model": "deepseek-stub-v1",
            # embedding_provider intentionally absent
            "schema_version": "v1",
        },
        "markets": [
            {
                "market_id": "m1",
                "condition_id": "cond-m1",
                "question": "Will A win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-m1-yes", "tok-m1-no"],
            },
            {
                "market_id": "m2",
                "condition_id": "cond-m2",
                "question": "Will B win?",
                "description": "",
                "end_date": "2026-11-03",
                "topic": "topic-01",
                "token_ids": ["tok-m2-yes", "tok-m2-no"],
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
            }
        ],
        "baskets": [
            {
                "basket_id": "basket-m1__m2",
                "token_ids": ["tok-m1-yes", "tok-m1-no", "tok-m2-yes", "tok-m2-no"],
                "expected_sum": 1.0,
                "dependency_basis": ["m1__m2"],
            }
        ],
    }
    # Must not raise — backward compatibility with pre-provenance artifacts
    validate_output_document(payload)


# ---------------------------------------------------------------------------
# 5. Config-layer fail-loud: DiscoveryConfig and load_config must both reject
#    a missing embedding_provider (not silently default to stub).
# ---------------------------------------------------------------------------

def test_discovery_config_raises_when_embedding_provider_omitted(tmp_path: Path) -> None:
    """DiscoveryConfig(output_root=...) without embedding_provider must raise ValueError.

    This prevents silent stub runs when a caller forgets the field — the
    previous default of 'stub' masked this class of misconfiguration entirely.
    """
    with pytest.raises(ValueError, match="embedding_provider"):
        DiscoveryConfig(output_root=tmp_path / "artifacts")


def test_load_config_raises_when_json_omits_embedding_provider_field(tmp_path: Path) -> None:
    """load_config must raise a clear ValueError when the JSON config file has no
    embedding_provider field — the same fail-loud standard applied at the factory layer.
    """
    config_payload = {
        "output_root": str(tmp_path / "artifacts"),
        # embedding_provider intentionally absent
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="embedding_provider"):
        load_config(config_path)
