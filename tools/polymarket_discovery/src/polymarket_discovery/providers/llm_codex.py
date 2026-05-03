from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Sequence

from ..contracts import MarketDescriptor
from ..interfaces.codex_invoker import CodexInvoker
from ..interfaces.llm_basket_group import LLMBasketGroup
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider
from ..interfaces.market_pair import MarketPair
from .llm_codec import (
    build_basket_prompt,
    build_batched_dependency_prompt,
    parse_batched_dependency_predictions,
    parse_llm_basket_groups,
)
from .settings import LLMProviderSettings


_BATCHED_SYSTEM_PREAMBLE = (
    "You infer market dependencies. You will receive a JSON object with a 'pairs' array. "
    "Each pair has a pair_id, left_market, and right_market. "
    "Reply with a single JSON object containing a 'predictions' array. "
    "Each element must echo back the pair_id and include edge_type, confidence, and rationale. "
    "edge_type must be one of mutually_exclusive, conditional, related. "
    "confidence must be a number from 0 to 1. "
    "You MUST return exactly one prediction for every pair_id in the input, in any order. "
    "Do not wrap the JSON in code fences or include any other text."
)

_BASKET_SYSTEM_PREAMBLE = (
    "You identify basket structure in prediction markets. "
    "Given a list of markets that share a topic and end date, identify subsets "
    "whose YES-token prices sum to 1.0 (complete outcome sets). "
    'Reply with a single JSON object containing a "baskets" array. '
    "Each element must have basket_id (string), market_ids (array of market_id strings), "
    "and rationale (string). Only include markets that genuinely form a complete outcome set. "
    'Return {"baskets": []} if no complete sets are found. '
    "Do not wrap the JSON in code fences or include any other text."
)


_FENCE_PREFIXES = ("```json", "```")


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("Codex response was empty")

    for prefix in _FENCE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip("\n")
            if text.endswith("```"):
                text = text[: -len("```")].rstrip()
            break

    start = text.find("{")
    if start == -1:
        raise ValueError("Codex response did not contain a JSON object")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Codex response did not contain a balanced JSON object")


@dataclass(slots=True)
class CodexCliLLMProvider(LLMProvider):
    settings: LLMProviderSettings
    invoker: CodexInvoker

    def infer_dependencies_batched(
        self,
        pairs: Sequence[MarketPair],
    ) -> list[LLMDependencyPrediction]:
        """Infer dependency metadata for a batch of market pairs via the Codex CLI."""
        if not pairs:
            return []
        user_prompt = build_batched_dependency_prompt(pairs)
        full_prompt = f"{_BATCHED_SYSTEM_PREAMBLE}\n\n{user_prompt}"
        raw = self.invoker.run(full_prompt, timeout_seconds=self.settings.timeout_seconds)
        json_text = _extract_json_object(raw)
        return parse_batched_dependency_predictions(json_text, expected_count=len(pairs))

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        """Ask the Codex CLI to identify N-way basket groupings for the topic group."""
        if len(markets) < 2:
            return []
        known_ids = frozenset(m.market_id for m in markets)
        user_prompt = build_basket_prompt(markets)
        full_prompt = f"{_BASKET_SYSTEM_PREAMBLE}\n\n{user_prompt}"
        raw = self.invoker.run(full_prompt, timeout_seconds=self.settings.timeout_seconds)
        json_text = _extract_json_object(raw)
        return parse_llm_basket_groups(json_text, known_market_ids=known_ids)


@dataclass(slots=True)
class SubprocessCodexInvoker(CodexInvoker):
    binary: str = "codex"
    base_args: tuple[str, ...] = ("exec",)
    use_json_flag: bool = True
    extra_env: dict[str, str] = field(default_factory=dict)

    def run(self, prompt: str, *, timeout_seconds: float) -> str:
        argv = [self.binary, *self.base_args]
        if self.use_json_flag:
            argv.append("--json")

        try:
            completed = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=self._build_env() if self.extra_env else None,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"codex binary not found: {self.binary}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"codex invocation timed out after {timeout_seconds}s"
            ) from exc

        if completed.returncode != 0:
            stderr_excerpt = (completed.stderr or "").strip()[:500]
            raise RuntimeError(
                f"codex exited {completed.returncode}: {stderr_excerpt}"
            )
        return completed.stdout

    def _build_env(self) -> dict[str, str]:
        import os

        env = dict(os.environ)
        env.update(self.extra_env)
        return env
