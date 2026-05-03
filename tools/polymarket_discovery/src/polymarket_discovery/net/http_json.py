from __future__ import annotations

import email.utils
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request
import urllib.request

from .rate_limiter import RateLimiter, get_default_limiter


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_SECONDS: float = 60.0


def _parse_retry_after(value: str | None) -> float | None:
    """Return the server-suggested wait in seconds, capped at MAX_RETRY_AFTER_SECONDS.

    Returns None when the header is absent or unparseable so callers fall back
    to exponential backoff without raising.
    """
    if value is None:
        return None
    try:
        seconds = float(value)
        return min(max(0.0, seconds), MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
        now = datetime.now(tz=timezone.utc)
        seconds = max(0.0, (dt - now).total_seconds())
        return min(seconds, MAX_RETRY_AFTER_SECONDS)
    except Exception:
        return None


@dataclass(slots=True)
class RetrySettings:
    max_attempts: int = 3
    backoff_seconds: float = 0.5
    backoff_factor: float = 2.0


def build_url(base_url: str, path: str, params: Mapping[str, str] | None = None) -> str:
    query = urlencode(dict(params or {}))
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        return f"{url}?{query}"
    return url


def request_json(
    *,
    url: str,
    timeout_seconds: float,
    retry: RetrySettings,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    retryable_status_codes: frozenset[int] = RETRYABLE_STATUS_CODES,
    limiter: RateLimiter | None = None,
) -> Any:
    encoded_payload = json.dumps(dict(payload)).encode("utf-8") if payload is not None else None

    request_headers = dict(headers or {})

    if encoded_payload is not None and "Content-Type" not in request_headers:
        request_headers["Content-Type"] = "application/json"

    _limiter = limiter if limiter is not None else get_default_limiter()

    host = urlparse(url).hostname or ""

    last_error: Exception | None = None

    for attempt in range(retry.max_attempts):
        _limiter.acquire(host)

        request = Request(url, data=encoded_payload, headers=request_headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")

            return json.loads(raw)
        
        except HTTPError as exc:
            if exc.code not in retryable_status_codes or attempt >= retry.max_attempts - 1:
                raise

            last_error = exc
            retry_after = _parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)

        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= retry.max_attempts - 1:
                raise
            
            last_error = exc
            retry_after = None

        sleep_seconds = retry.backoff_seconds * (retry.backoff_factor**attempt)

        if retry_after is not None:
            # Never sleep less than the local minimum — servers under load sometimes lie low.
            sleep_seconds = max(retry_after, sleep_seconds)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if last_error is not None:
        raise last_error
    
    raise RuntimeError("request retry loop exited unexpectedly")
