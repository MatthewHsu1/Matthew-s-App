from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None

    @classmethod
    def allow(cls) -> "Decision":
        return cls(allowed=True, reason=None)

    @classmethod
    def block(cls, reason: str) -> "Decision":
        if not reason or not reason.strip():
            raise ValueError("block() requires a non-empty reason")
        return cls(allowed=False, reason=reason)
