from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def touch_kill_switch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def clear_kill_switch(path: Path) -> None:
    if path.exists():
        path.unlink()


def is_kill_switch_set(paths: Iterable[Path]) -> bool:
    return any(Path(p).exists() for p in paths)
