from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from alpha_engine.config.paths import EnvPaths


def _templates_dir() -> Path:
    return Path(str(resources.files("alpha_engine"))) / ".." / ".." / "configs" / "templates"


def run(*, envs_root: Path, name: str, template: str) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    if paths.env_dir.exists():
        print(f"error: env {name!r} already exists at {paths.env_dir}", flush=True)
        return 1

    tmpl_path = (_templates_dir() / f"{template}.json").resolve()
    if not tmpl_path.exists():
        print(f"error: template {template!r} not found at {tmpl_path}", flush=True)
        return 1

    paths.ensure_dirs()
    raw = json.loads(tmpl_path.read_text(encoding="utf-8"))
    raw["env_name"] = name
    paths.config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    paths.secrets_path.write_text(
        "# Per-env secrets (gitignored). Keys here are loaded into the engine process.\n",
        encoding="utf-8",
    )
    print(f"created env {name!r} at {paths.env_dir}", flush=True)
    return 0
