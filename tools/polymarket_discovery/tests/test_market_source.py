from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from polymarket_discovery.components import FixtureMarketSource, build_components
from polymarket_discovery.config import DiscoveryConfig
from polymarket_discovery.sources.polymarket import PolymarketMarketSource


@dataclass
class _FakeResponse:
    payload: object

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _config(tmp_path: Path, **params: object) -> DiscoveryConfig:
    return DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="polymarket-api",
        embedding_provider="stub",
        params=dict(params),
    )


def _fixture_payload(name: str) -> object:
    path = ROOT / "tests" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_market_source_still_uses_configured_markets(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        markets=[
            {
                "market_id": "fixture-a",
                "condition_id": "cond-fixture-a",
                "question": "Fixture market A?",
                "description": "Fixture",
                "end_date": "2026-11-03",
                "topic": "fixture",
                "token_ids": ["tok-fixture-a"],
            }
        ],
    )

    markets = FixtureMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["fixture-a"]
    assert markets[0].token_ids == ["tok-fixture-a"]


def test_polymarket_source_normalizes_and_filters_active_markets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gamma_payload = _fixture_payload("gamma_markets_page1.json")
    clob_payload = _fixture_payload("clob_simplified_markets_page1.json")
    requested_urls: list[str] = []
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 2,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        requested_urls.append(url)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["mkt-a", "mkt-b"]
    assert [market.condition_id for market in markets] == ["cond-a", "cond-b"]
    assert [market.question for market in markets] == ["Will Candidate A win?", "Will Candidate B win?"]
    assert [market.end_date for market in markets] == ["2026-11-03", "2026-11-03T23:59:59Z"]
    assert markets[0].token_ids == ["tok-a-no", "tok-a-yes"]
    assert markets[1].token_ids == ["tok-b-no", "tok-b-yes"]
    assert any(
        url.startswith("https://clob.polymarket.com/simplified-markets?")
        and "limit=2" in url
        for url in requested_urls
    )


def test_polymarket_source_skips_malformed_and_inactive_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gamma_payload = [
        {
            "id": "mkt-good",
            "question": "Will the test pass?",
            "conditionId": "cond-good",
            "slug": "test-pass",
            "description": "Good market",
            "resolutionSource": "Source",
            "endDate": "2026-11-04T00:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
            "clobTokenIds": ["tok-good"],
        },
        {
            "id": "mkt-inactive",
            "question": "Will the test fail?",
            "conditionId": "cond-inactive",
            "slug": "test-fail",
            "description": "Inactive market",
            "resolutionSource": "Source",
            "endDate": "2026-11-04T00:00:00Z",
            "category": "testing",
            "active": False,
            "closed": False,
            "archived": False,
        },
        {
            "id": "mkt-malformed",
            "question": "Missing condition",
            "slug": "test-missing",
            "description": "Malformed market",
            "resolutionSource": "Source",
            "endDate": "2026-11-04T00:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        },
    ]
    clob_payload = {"limit": 1, "next_cursor": None, "count": 1, "data": []}
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["mkt-good"]


def test_polymarket_source_orders_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gamma_payload = [
        {
            "id": "mkt-z",
            "question": "Will Z happen?",
            "conditionId": "cond-z",
            "slug": "z",
            "description": "Z market",
            "resolutionSource": "Source",
            "endDate": "2026-12-01T00:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        },
        {
            "id": "mkt-a",
            "question": "Will A happen?",
            "conditionId": "cond-a",
            "slug": "a",
            "description": "A market",
            "resolutionSource": "Source",
            "endDate": "2026-11-01T00:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        },
    ]
    clob_payload = {
        "limit": 10,
        "next_cursor": None,
        "count": 2,
        "data": [
            {
                "condition_id": "cond-z",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-z"}],
            },
            {
                "condition_id": "cond-a",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-a"}],
            },
        ],
    }
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["mkt-a", "mkt-z"]
    assert [market.end_date for market in markets] == ["2026-11-01T00:00:00Z", "2026-12-01T00:00:00Z"]


def test_polymarket_source_stops_on_repeated_clob_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gamma_payload = [
        {
            "id": "mkt-a",
            "question": "Will A happen?",
            "conditionId": "cond-a",
            "slug": "a",
            "description": "A market",
            "resolutionSource": "Source",
            "endDate": "2026-11-01T00:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        }
    ]
    clob_calls: list[str] = []
    clob_payload_1 = {
        "limit": 10,
        "next_cursor": "cursor-1",
        "count": 1,
        "data": [
            {
                "condition_id": "cond-a",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-a"}],
            }
        ],
    }
    clob_payload_2 = {
        "limit": 10,
        "next_cursor": "cursor-2",
        "count": 1,
        "data": [
            {
                "condition_id": "cond-a",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-a"}],
            }
        ],
    }
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            clob_calls.append(url)
            if len(clob_calls) == 1:
                return _FakeResponse(clob_payload_1)
            if len(clob_calls) == 2:
                return _FakeResponse(clob_payload_2)
            raise AssertionError(f"unexpected repeated CLOB request: {url}")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["mkt-a"]
    assert clob_calls == [
        "https://clob.polymarket.com/simplified-markets?limit=10",
        "https://clob.polymarket.com/simplified-markets?limit=10&next_cursor=cursor-1",
    ]


def test_polymarket_source_orders_same_day_by_timestamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gamma_payload = [
        {
            "id": "mkt-late",
            "question": "Will later happen?",
            "conditionId": "cond-late",
            "slug": "late",
            "description": "Late market",
            "resolutionSource": "Source",
            "endDate": "2026-11-04T23:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        },
        {
            "id": "mkt-early",
            "question": "Will earlier happen?",
            "conditionId": "cond-early",
            "slug": "early",
            "description": "Early market",
            "resolutionSource": "Source",
            "endDate": "2026-11-04T01:00:00Z",
            "category": "testing",
            "active": True,
            "closed": False,
            "archived": False,
        },
    ]
    clob_payload = {
        "limit": 10,
        "next_cursor": None,
        "count": 2,
        "data": [
            {
                "condition_id": "cond-late",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-late"}],
            },
            {
                "condition_id": "cond-early",
                "active": True,
                "closed": False,
                "archived": False,
                "accepting_orders": True,
                "tokens": [{"token_id": "tok-early"}],
            },
        ],
    }
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert [market.market_id for market in markets] == ["mkt-early", "mkt-late"]


def test_polymarket_source_surfaces_retryable_transport_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 0,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        raise URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(URLError):
        PolymarketMarketSource().fetch_active_markets(config)


def test_normalizer_populates_description_from_gamma_description_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """description must be populated from Gamma's description field (the structured
    resolution criteria).  resolution_source must carry the short attribution label
    from resolutionSource — the two fields must be distinct.
    """
    resolution_criteria = (
        "This market resolves YES if the named candidate wins the presidency "
        "as certified by the Electoral College. Otherwise resolves NO."
    )
    gamma_payload = [
        {
            "id": "mkt-x",
            "question": "Will Candidate X win?",
            "conditionId": "cond-x",
            "slug": "candidate-x",
            "description": resolution_criteria,
            "resolutionSource": "Official results",
            "endDate": "2026-11-04T00:00:00Z",
            "category": "politics",
            "active": True,
            "closed": False,
            "archived": False,
            "clobTokenIds": ["tok-x"],
        },
    ]
    clob_payload = {"limit": 10, "next_cursor": None, "count": 0, "data": []}
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert len(markets) == 1
    market = markets[0]
    # description must contain the full resolution criteria text
    assert market.description == resolution_criteria, (
        f"Expected description to contain resolution criteria text, got: {market.description!r}"
    )
    # resolution_source must carry the attribution label, not the full criteria
    assert market.resolution_source == "Official results", (
        f"Expected resolution_source='Official results', got: {market.resolution_source!r}"
    )
    # MarketDescriptor must no longer have a 'rules' attribute
    assert not hasattr(market, "rules"), (
        "MarketDescriptor must not have a 'rules' attribute"
    )


def test_normalizer_resolution_source_empty_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A market with no resolutionSource should produce an empty resolution_source
    field (not an error), and an empty description field when description is absent.
    """
    gamma_payload = [
        {
            "id": "mkt-nodesc",
            "question": "Will X happen?",
            "conditionId": "cond-nodesc",
            "slug": "x",
            "description": "",
            "resolutionSource": "FBI website",
            "endDate": "2026-11-04T00:00:00Z",
            "category": "crime",
            "active": True,
            "closed": False,
            "archived": False,
            "clobTokenIds": ["tok-nodesc"],
        },
    ]
    clob_payload = {"limit": 10, "next_cursor": None, "count": 0, "data": []}
    config = _config(
        tmp_path,
        polymarket={
            "gamma_base_url": "https://gamma-api.polymarket.com",
            "clob_base_url": "https://clob.polymarket.com",
            "page_size": 10,
            "timeout_seconds": 1,
            "retries": 1,
            "backoff_seconds": 0,
        },
    )

    def fake_urlopen(request, timeout=0):
        url = getattr(request, "full_url", request)
        if "gamma-api.polymarket.com/markets" in url:
            return _FakeResponse(gamma_payload)
        if "clob.polymarket.com/simplified-markets" in url:
            return _FakeResponse(clob_payload)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    markets = PolymarketMarketSource().fetch_active_markets(config)

    assert len(markets) == 1
    assert markets[0].description == "", "description must be empty string when no description is present"
    assert markets[0].resolution_source == "FBI website", "resolution_source must be populated from resolutionSource"


# ---------------------------------------------------------------------------
# Fail-loud: build_components must not silently fall back to fixture data
# ---------------------------------------------------------------------------

def test_build_components_raises_when_config_is_none() -> None:
    """build_components(None) must not silently return a fixture-backed pipeline."""
    with pytest.raises(ValueError, match="No market source configured"):
        build_components(None)


def test_build_components_raises_when_market_source_is_empty(tmp_path: Path) -> None:
    """A DiscoveryConfig whose market_source was cleared to an empty string must
    also fail loudly.  The 'fixture' value must be an explicit opt-in, not the
    result of an accidental empty field.
    """
    # DiscoveryConfig enforces non-empty embedding_provider but not market_source at
    # construction time (market_source has a live default).  We bypass that by using
    # object.__setattr__ on the frozen dataclass so we can test the factory guard.
    config = DiscoveryConfig(
        output_root=tmp_path / "artifacts",
        market_source="polymarket-api",
        embedding_provider="stub",
    )
    object.__setattr__(config, "market_source", "")
    with pytest.raises(ValueError, match="No market source configured"):
        build_components(config)


# ---------------------------------------------------------------------------
# Provenance: run_metadata.market_source must reflect the explicit opt-in
# ---------------------------------------------------------------------------

def test_run_artifact_records_fixture_market_source_when_explicitly_configured(
    tmp_path: Path,
) -> None:
    """A full pipeline run with market_source='fixture' must record 'fixture' in
    run_metadata.market_source of the output artifact.  This proves the provenance
    field is stamped from config, not hardcoded.
    """
    import json
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
    assert payload["run_metadata"]["market_source"] == "fixture", (
        "Artifact must record market_source='fixture' for fixture runs so Phase 2 "
        "consumers can filter them out."
    )
