from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request
import urllib.request


RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


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
) -> Any:
    encoded_payload = json.dumps(dict(payload)).encode("utf-8") if payload is not None else None
    request_headers = dict(headers or {})
    if encoded_payload is not None and "Content-Type" not in request_headers:
        request_headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(retry.max_attempts):
        request = Request(url, data=encoded_payload, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw)
        except HTTPError as exc:
            if exc.code not in retryable_status_codes or attempt >= retry.max_attempts - 1:
                raise
            last_error = exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt >= retry.max_attempts - 1:
                raise
            last_error = exc

        sleep_seconds = retry.backoff_seconds * (retry.backoff_factor**attempt)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if last_error is not None:
        raise last_error
    raise RuntimeError("request retry loop exited unexpectedly")
