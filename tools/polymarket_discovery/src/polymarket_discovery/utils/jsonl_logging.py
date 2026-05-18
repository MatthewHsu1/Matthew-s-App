from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

PACKAGE_LOGGER_NAME = "polymarket_discovery"


_RESERVED_LOGRECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


class RunIdFilter(logging.Filter):
    """Stamps every record with a fixed run_id."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


def setup_jsonl_logging(*, path: Path, run_id: str) -> JsonlHandler:
    """Attach a JsonlHandler stamped with run_id to the package logger."""
    handler = JsonlHandler(path=path)
    handler.addFilter(RunIdFilter(run_id=run_id))
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.addHandler(handler)
    if logger.level == logging.NOTSET or logger.level > logging.INFO:
        logger.setLevel(logging.INFO)
    return handler


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Context manager that emits stage_started / stage_completed (or _failed) records."""
    log = logging.getLogger(PACKAGE_LOGGER_NAME)
    started = time.perf_counter()
    log.info("stage_started", extra={"stage": name})
    try:
        yield
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "stage_failed",
            extra={
                "stage": name,
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    else:
        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "stage_completed",
            extra={"stage": name, "duration_ms": duration_ms},
        )


class JsonlHandler(logging.Handler):
    """Append-only logging.Handler that writes one JSON object per line."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _RESERVED_LOGRECORD_ATTRS
        }
        payload = {
            **extras,
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "event": record.getMessage(),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True, default=str))
            fh.write("\n")
