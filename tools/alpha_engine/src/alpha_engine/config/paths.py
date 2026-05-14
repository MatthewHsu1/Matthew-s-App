from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ENV_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass(frozen=True)
class EnvPaths:
    envs_root: Path
    env_name: str

    def __post_init__(self) -> None:
        if not _ENV_NAME_RE.match(self.env_name):
            raise ValueError(
                f"env_name must match {_ENV_NAME_RE.pattern}; got: {self.env_name!r}"
            )

    @property
    def env_dir(self) -> Path:
        return Path(self.envs_root) / self.env_name

    @property
    def config_path(self) -> Path:
        return self.env_dir / "config.json"

    @property
    def secrets_path(self) -> Path:
        return self.env_dir / "secrets.env"

    @property
    def state_dir(self) -> Path:
        return self.env_dir / "state"

    @property
    def logs_dir(self) -> Path:
        return self.env_dir / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.env_dir / "reports"

    @property
    def kill_switch_path(self) -> Path:
        return self.env_dir / ".KILL"

    @property
    def last_run_path(self) -> Path:
        return self.state_dir / "last_run.json"

    def ensure_dirs(self) -> None:
        for d in (self.state_dir, self.logs_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)
