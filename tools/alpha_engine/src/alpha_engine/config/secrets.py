from __future__ import annotations

import os
from pathlib import Path


class SecretsError(RuntimeError):
    """Raised when required secrets are missing from the environment."""


def load_secrets_file(path: Path) -> None:
    """Read KEY=VALUE lines from `path` and set them on os.environ.

    Existing env vars are NOT overwritten — env-set values win over file values.
    Missing files are a no-op (operator may already have exported vars manually).
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_required_env_vars(required: dict[str, str]) -> dict[str, str]:
    """Resolve env var names → values. Raises SecretsError on missing.

    `required` maps logical name → env var name, e.g. {"username": "IBKR_USERNAME"}.
    Returns the same mapping with values substituted.
    """
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for logical, env_name in required.items():
        val = os.environ.get(env_name)
        if val is None or val == "":
            missing.append(env_name)
        else:
            resolved[logical] = val
    if missing:
        raise SecretsError(
            f"required env vars not set: {', '.join(sorted(missing))}. "
            "Check the env's secrets.env file."
        )
    return resolved
