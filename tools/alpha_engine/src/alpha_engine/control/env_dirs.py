from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class EnvSummary:
    name: str
    mode: str | None
    last_run_status: str | None


def iter_envs(envs_root: Path) -> Iterator[EnvSummary]:
    if not envs_root.exists():
        return
    for child in sorted(envs_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        mode = None
        cfg = child / "config.json"
        if cfg.exists():
            try:
                mode = json.loads(cfg.read_text(encoding="utf-8")).get("mode")
            except Exception:
                mode = "<invalid>"
        last_run_status = None
        lr = child / "state" / "last_run.json"
        if lr.exists():
            try:
                last_run_status = json.loads(lr.read_text(encoding="utf-8")).get("status")
            except Exception:
                last_run_status = "<invalid>"
        yield EnvSummary(name=child.name, mode=mode, last_run_status=last_run_status)
