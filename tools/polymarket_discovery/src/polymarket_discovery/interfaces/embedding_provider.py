from __future__ import annotations

from typing import Protocol
from typing import Sequence


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embedding vectors in input order."""
