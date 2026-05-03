from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence
from urllib.error import HTTPError

from ..contracts import MarketDescriptor
from ..interfaces.market_source import MarketSource
from ..net.http_json import RetrySettings, build_url, request_json
from ..utils.coercion import coerce_bool, coerce_float, coerce_int, coerce_optional_int, coerce_str


@dataclass(slots=True)
class PolymarketSourceSettings:
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_base_url: str = "https://clob.polymarket.com"
    timeout_seconds: float = 10.0
    retry: RetrySettings = field(default_factory=lambda: RetrySettings(max_attempts=4, backoff_seconds=0.5, backoff_factor=2.0))
    page_size: int = 100
    max_markets: int | None = None


@dataclass(slots=True)
class _NormalizedCLOBMarket:
    condition_id: str
    token_ids: list[str] = field(default_factory=list)
    active: bool = True
    closed: bool = False
    archived: bool = False
    accepting_orders: bool = True


@dataclass(slots=True)
class PolymarketMarketSource(MarketSource):
    """Fetch and normalize active markets from Gamma plus CLOB metadata."""

    def fetch_active_markets(self, config: Any | None = None) -> list[MarketDescriptor]:
        settings = self._resolve_settings(config)
        gamma_markets = self._fetch_gamma_markets(settings)

        # Collect the unique condition_ids present in the Gamma result, then look
        # each one up individually against the CLOB /markets/{condition_id} endpoint.
        # This avoids bulk-scanning tens of thousands of CLOB markets just to join
        # a few hundred that Gamma returned.
        seen_condition_ids: dict[str, _NormalizedCLOBMarket | None] = {}
        for raw_market in gamma_markets:
            cid = self._string_field(raw_market, "conditionId", "condition_id")
            if cid and cid not in seen_condition_ids:
                seen_condition_ids[cid] = self._fetch_clob_market(cid, settings)

        normalized: list[MarketDescriptor] = []
        seen_market_ids: set[str] = set()
        for raw_market in gamma_markets:
            cid = self._string_field(raw_market, "conditionId", "condition_id")
            clob_market = seen_condition_ids.get(cid) if cid else None
            market = self._normalize_market(raw_market, clob_market)
            if market is None or market.market_id in seen_market_ids:
                continue
            seen_market_ids.add(market.market_id)
            normalized.append(market)

        normalized.sort(key=self._sort_key)
        if settings.max_markets is not None:
            return normalized[: settings.max_markets]
        return normalized

    def _resolve_settings(self, config: Any | None) -> PolymarketSourceSettings:
        params = getattr(config, "params", {}) if config is not None else {}
        if not isinstance(params, dict):
            params = {}

        source_params: dict[str, Any] = params
        for key in ("polymarket", "market_source", "polymarket_api"):
            candidate = params.get(key)
            if isinstance(candidate, dict):
                source_params = candidate
                break

        retries = coerce_int(source_params.get("retries"), 3)
        settings = PolymarketSourceSettings(
            gamma_base_url=coerce_str(source_params.get("gamma_base_url"), "https://gamma-api.polymarket.com"),
            clob_base_url=coerce_str(source_params.get("clob_base_url"), "https://clob.polymarket.com"),
            timeout_seconds=coerce_float(source_params.get("timeout_seconds"), 10.0),
            retry=RetrySettings(
                max_attempts=retries + 1,
                backoff_seconds=coerce_float(source_params.get("backoff_seconds"), 0.5),
                backoff_factor=coerce_float(source_params.get("backoff_factor"), 2.0),
            ),
            page_size=coerce_int(source_params.get("page_size"), 100),
            max_markets=coerce_optional_int(source_params.get("max_markets")),
        )
        if settings.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if retries < 0:
            raise ValueError("retries must be zero or greater")
        if settings.retry.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be zero or greater")
        if settings.retry.backoff_factor <= 0:
            raise ValueError("backoff_factor must be greater than zero")
        if settings.page_size <= 0:
            raise ValueError("page_size must be greater than zero")
        if settings.max_markets is not None and settings.max_markets < 0:
            raise ValueError("max_markets must be zero or greater")
        return settings

    def _fetch_gamma_markets(self, settings: PolymarketSourceSettings) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        offset = 0
        seen_fingerprints: set[tuple[str, ...]] = set()
        while True:
            payload = self._request_json(
                settings.gamma_base_url,
                "/markets",
                settings,
                params={
                    "active": "true",
                    "closed": "false",
                    "order": "endDate",
                    "ascending": "true",
                    "limit": str(settings.page_size),
                    "offset": str(offset),
                },
            )
            page = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(page, list) or not page:
                break
            fingerprint = tuple(self._string_field(item, "id", "market_id") for item in page if isinstance(item, dict))
            if fingerprint and fingerprint in seen_fingerprints:
                break
            if fingerprint:
                seen_fingerprints.add(fingerprint)
            for item in page:
                if isinstance(item, dict):
                    markets.append(item)
            if offset == 0 and len(page) > settings.page_size:
                break
            if len(page) < settings.page_size:
                break
            offset += len(page)
        return markets

    def _fetch_clob_market(self, condition_id: str, settings: PolymarketSourceSettings) -> _NormalizedCLOBMarket | None:
        """Fetch CLOB metadata for a single condition_id.

        Returns None when the condition_id is absent from the order book (404),
        which causes _is_active to treat the market as not tradable.  This is
        intentional: a market that Gamma knows about but the CLOB has never
        listed is not safely tradable, so we drop it rather than letting it
        through silently.
        """
        try:
            payload = self._request_json(
                settings.clob_base_url,
                f"/markets/{condition_id}",
                settings,
            )
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        return self._normalize_clob_market(payload)

    def _request_json(
        self,
        base_url: str,
        path: str,
        settings: PolymarketSourceSettings,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        return request_json(
            url=build_url(base_url, path, params),
            timeout_seconds=settings.timeout_seconds,
            retry=settings.retry,
            method="GET",
            headers={"User-Agent": "polymarket-discovery/0.1"},
        )

    def _normalize_market(
        self,
        raw_market: dict[str, Any],
        clob_market: _NormalizedCLOBMarket | None,
    ) -> MarketDescriptor | None:
        if not self._is_active(raw_market, clob_market):
            return None

        market_id = self._string_field(raw_market, "id", "market_id")
        condition_id = self._string_field(raw_market, "conditionId", "condition_id")
        if not condition_id and clob_market is not None:
            condition_id = clob_market.condition_id
        question = self._string_field(raw_market, "question", "title")
        end_date = self._string_field(raw_market, "endDate", "end_date", "endDateIso", "umaEndDateIso")
        if not market_id or not condition_id or not question or not end_date:
            return None

        token_ids = self._collect_token_ids(raw_market, clob_market)
        if not token_ids:
            return None

        description = self._string_field(raw_market, "description", "subtitle")
        
        # `resolutionSource` is a short attribution label (e.g. "Official results",
        # a bare URL) that identifies who/what decides resolution.  It is preserved
        # for downstream signal but kept out of the embedding/LLM-prompt pipeline.
        resolution_source = self._string_field(raw_market, "resolutionSource", "resolution_source")
        topic = self._string_field(raw_market, "category", "subcategory")
        if not topic:
            topic = "unassigned"

        return MarketDescriptor(
            market_id=market_id,
            condition_id=condition_id,
            question=question,
            description=description,
            end_date=end_date,
            topic=topic,
            token_ids=token_ids,
            resolution_source=resolution_source,
        )

    def _normalize_clob_market(self, raw_market: Any) -> _NormalizedCLOBMarket | None:
        if not isinstance(raw_market, dict):
            return None

        condition_id = self._string_field(raw_market, "condition_id", "conditionId")
        if not condition_id:
            return None

        token_ids: list[str] = []
        raw_tokens = raw_market.get("tokens")
        if isinstance(raw_tokens, list):
            for token in raw_tokens:
                token_id = self._string_field(token, "token_id", "tokenId") if isinstance(token, dict) else self._coerce_token_id(token)
                if token_id:
                    token_ids.append(token_id)

        return _NormalizedCLOBMarket(
            condition_id=condition_id,
            token_ids=self._dedupe_preserve_order(token_ids),
            active=coerce_bool(raw_market.get("active"), True),
            closed=coerce_bool(raw_market.get("closed"), False),
            archived=coerce_bool(raw_market.get("archived"), False),
            accepting_orders=coerce_bool(raw_market.get("accepting_orders"), True),
        )

    def _collect_token_ids(self, raw_market: dict[str, Any], clob_market: _NormalizedCLOBMarket | None) -> list[str]:
        token_ids: list[str] = []
        if clob_market is not None:
            token_ids.extend(clob_market.token_ids)
        token_ids.extend(self._token_ids_from_value(raw_market.get("clobTokenIds")))
        return self._dedupe_preserve_order(token_ids)

    def _token_ids_from_value(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            token_ids: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    token_id = self._string_field(item, "token_id", "tokenId")
                else:
                    token_id = self._coerce_token_id(item)
                if token_id:
                    token_ids.append(token_id)
            return token_ids
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return self._token_ids_from_value(parsed)
            if cleaned.startswith("[") and cleaned.endswith("]"):
                inner = cleaned[1:-1].strip()
                if not inner:
                    return []
                return [token.strip().strip('"').strip("'") for token in inner.split(",") if token.strip().strip('"').strip("'")]
            return [cleaned]
        return []

    @staticmethod
    def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    @staticmethod
    def _is_active(raw_market: dict[str, Any], clob_market: _NormalizedCLOBMarket | None) -> bool:
        if not coerce_bool(raw_market.get("active"), False):
            return False
        if coerce_bool(raw_market.get("closed"), False):
            return False
        if coerce_bool(raw_market.get("archived"), False):
            return False
        if clob_market is None:
            return False
        if not clob_market.active or clob_market.closed or clob_market.archived:
            return False
        if not clob_market.accepting_orders:
            return False
        return True

    @staticmethod
    def _sort_key(market: MarketDescriptor) -> tuple[str, str]:
        normalized_end_date = PolymarketMarketSource._sort_timestamp(market.end_date)
        if normalized_end_date is not None:
            return (normalized_end_date.isoformat(), market.market_id)
        return ("~" + (market.end_date or ""), market.market_id)

    @staticmethod
    def _sort_timestamp(value: str) -> datetime | None:
        cleaned = (value or "").strip()
        if not cleaned:
            return None
        try:
            if len(cleaned) == 10 and cleaned.count("-") == 2 and "T" not in cleaned:
                normalized = f"{cleaned}T00:00:00+00:00"
            else:
                normalized = cleaned[:-1] + "+00:00" if cleaned.endswith("Z") else cleaned

            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            return None

    @staticmethod
    def _string_field(raw: Any, *keys: str) -> str:
        if not isinstance(raw, dict):
            return ""
        for key in keys:
            value = raw.get(key)
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
        return ""

    @staticmethod
    def _coerce_token_id(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""
