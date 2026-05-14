from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path


PACKAGE_LOGGER_NAME = "alpha_engine"


_RESERVED_LOGRECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


class _StaticContextFilter(logging.Filter):
    def __init__(self, *, run_id: str, env_name: str, mode: str) -> None:
        super().__init__()
        self._fields = {"run_id": run_id, "env_name": env_name, "mode": mode}

    def filter(self, record: logging.LogRecord) -> bool:
        for k, v in self._fields.items():
            setattr(record, k, v)
        return True


class JsonlHandler(logging.Handler):
    """Append-only logging.Handler writing one JSON object per line."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            extras = {
                k: v
                for k, v in record.__dict__.items()
                if k not in _RESERVED_LOGRECORD_ATTRS
            }
            payload = {
                **extras,
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "event": record.getMessage(),
                "level": record.levelname,
            }
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True, default=str))
                fh.write("\n")
        except Exception:  # pragma: no cover — logging must never raise into caller
            self.handleError(record)


def setup_jsonl_logging(
    *, path: Path, run_id: str, env_name: str, mode: str
) -> JsonlHandler:
    handler = JsonlHandler(path=Path(path))
    handler.addFilter(_StaticContextFilter(run_id=run_id, env_name=env_name, mode=mode))
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.addHandler(handler)
    if logger.level == logging.NOTSET or logger.level > logging.INFO:
        logger.setLevel(logging.INFO)
    return handler
