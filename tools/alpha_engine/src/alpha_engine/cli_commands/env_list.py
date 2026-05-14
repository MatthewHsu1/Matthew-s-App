from __future__ import annotations

from pathlib import Path

from alpha_engine.control.env_dirs import iter_envs


def run(*, envs_root: Path) -> int:
    rows = list(iter_envs(envs_root))
    if not rows:
        print("no envs found.", flush=True)
        return 0
    print(f"{'NAME':<24} {'MODE':<10} {'LAST_RUN':<16}", flush=True)
    for r in rows:
        print(
            f"{r.name:<24} {r.mode or '-':<10} {r.last_run_status or '-':<16}",
            flush=True,
        )
    return 0
