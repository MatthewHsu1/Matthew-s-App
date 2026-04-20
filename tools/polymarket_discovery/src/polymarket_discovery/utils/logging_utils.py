from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, Iterator


@dataclass(slots=True)
class JsonlStageLogger:
    """Append-only structured logger for stage lifecycle events."""

    path: Path
    run_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, *, event: str, stage: str | None = None, **fields: Any) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "event": event,
        }
        if stage is not None:
            record["stage"] = stage
        if fields:
            record.update(fields)

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, default=str))
            fh.write("\n")

    @contextmanager
    def stage(self, stage_name: str) -> Iterator[None]:
        started = time.perf_counter()
        self.log(event="stage_started", stage=stage_name)
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.log(
                event="stage_failed",
                stage=stage_name,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise
        else:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.log(event="stage_completed", stage=stage_name, duration_ms=duration_ms)
