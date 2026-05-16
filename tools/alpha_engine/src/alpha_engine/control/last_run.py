from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class LastRunWriter:
    def __init__(self, path: Path):
        self._path = Path(path)

    def write(
        self,
        *,
        pid: int,
        started_ts: datetime,
        mode: str,
        run_id: str,
        env_name: str,
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(tz=timezone.utc)
        payload = {
            "pid": pid,
            "started_ts": started_ts.isoformat(),
            "mode": mode,
            "run_id": run_id,
            "env_name": env_name,
            "heartbeat_ts": now.isoformat(),
        }
        self._path.write_text(json.dumps(payload, indent=2))

    def heartbeat(self, now: datetime | None = None) -> None:
        if not self._path.exists():
            return
        ts = (now or datetime.now(tz=timezone.utc)).isoformat()
        data = json.loads(self._path.read_text())
        data["heartbeat_ts"] = ts
        self._path.write_text(json.dumps(data, indent=2))


def read_last_run(path: Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())
