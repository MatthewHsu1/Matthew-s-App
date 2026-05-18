from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


def generate_run_id(*, env_name: str, config_payload: dict[str, Any]) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = json.dumps(
        {"env": env_name, "config": config_payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"run_{now}_{digest}"
