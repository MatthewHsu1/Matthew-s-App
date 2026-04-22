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

from polymarket_discovery.components import FixtureMarketSource
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
                "rules": "Fixture rules",
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
