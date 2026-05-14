from __future__ import annotations

from pathlib import Path

from alpha_engine.control.kill_switch_file import touch_kill_switch


def run(*, envs_root: Path) -> int:
    target = envs_root / ".KILL"
    touch_kill_switch(target)
    print(f"kill-switch activated: {target}", flush=True)
    print("running engines will halt on their next event loop tick.", flush=True)
    print(f"to recover: rm {target}", flush=True)
    return 0
