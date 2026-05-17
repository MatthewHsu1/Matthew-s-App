from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from alpha_engine.config.paths import EnvPaths


def _read_template(name: str) -> str | None:
    res = resources.files("alpha_engine.configs.templates").joinpath(f"{name}.json")
    if not res.is_file():
        return None
    return res.read_text(encoding="utf-8")


def run(*, envs_root: Path, name: str, template: str) -> int:
    paths = EnvPaths(envs_root=envs_root, env_name=name)
    if paths.env_dir.exists():
        print(f"error: env {name!r} already exists at {paths.env_dir}", flush=True)
        return 1

    template_text = _read_template(template)
    if template_text is None:
        print(
            f"error: template {template!r} not found in alpha_engine.configs.templates",
            flush=True,
        )
        return 1

    paths.ensure_dirs()
    raw = json.loads(template_text)
    raw["env_name"] = name
    paths.config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    paths.secrets_path.write_text(
        "# Per-env secrets (gitignored). Keys here are loaded into the engine process.\n",
        encoding="utf-8",
    )
    print(f"created env {name!r} at {paths.env_dir}", flush=True)
    return 0
