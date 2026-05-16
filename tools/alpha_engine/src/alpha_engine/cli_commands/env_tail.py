from __future__ import annotations

from pathlib import Path

from alpha_engine.config.paths import EnvPaths
from alpha_engine.control.lifecycle import tail_jsonl

VALID_STREAMS = ("engine", "orders", "risk")


def run(*, envs_root: Path, name: str, stream: str = "engine", follow: bool = True) -> int:
    if stream not in VALID_STREAMS:
        print(f"unknown stream {stream!r}; valid: {VALID_STREAMS}", flush=True)
        return 2
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    log_path = paths.logs_dir / f"{stream}.jsonl"
    if not log_path.exists() and not follow:
        print(f"no log at {log_path}", flush=True)
        return 1
    try:
        for line in tail_jsonl(log_path, follow=follow):
            print(line, flush=True)
    except KeyboardInterrupt:
        return 0
    return 0
