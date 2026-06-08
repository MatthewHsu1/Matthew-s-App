from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

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

# Resolved once at module load; stable for the lifetime of the process.
_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_DEPENDENCY_SCHEMA_PATH = _SCHEMAS_DIR / "dependency_predictions.json"
_BASKET_SCHEMA_PATH = _SCHEMAS_DIR / "basket_groups.json"

_BATCHED_SYSTEM_PREAMBLE = (
    "You infer market dependencies. You will receive a JSON object with a 'pairs' array. "
    "Each pair has a pair_id, left_market, and right_market. "
    "For every pair, determine the edge_type (mutually_exclusive, conditional, or related), "
    "a confidence score from 0 to 1, and a rationale. "
    "You MUST return exactly one prediction for every pair_id in the input, echoing the pair_id verbatim."
)

_BASKET_SYSTEM_PREAMBLE = (
    "You identify basket structure in prediction markets. "
    "Given a list of markets that share a topic and end date, identify subsets "
    "whose YES-token prices sum to 1.0 (complete outcome sets). "
    "Only include markets that genuinely form a complete outcome set. "
    "Return an empty baskets array if no complete sets are found."
)


_FENCE_PREFIXES = ("```json", "```")


@dataclass(slots=True, frozen=True)
class CodexUsage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int


@dataclass(slots=True, frozen=True)
class CodexInvocationResult:
    text: str
    usage: CodexUsage | None


def _parse_jsonl_response(raw: str) -> CodexInvocationResult:
    """Parse a codex ``--json`` JSONL stream and extract the agent message.

    Rules:
    - Lines that are not valid JSON are silently skipped.
    - If multiple ``agent_message`` items exist, the last one wins (final turn).
    - Raises ``RuntimeError`` if no ``agent_message`` item is found.
    - ``usage`` is ``None`` when no ``turn.completed`` event is present.
    """
    last_agent_text: str | None = None
    usage: CodexUsage | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(event, dict):
            continue

        event_type = event.get("type")

        if event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    last_agent_text = text

        elif event_type == "turn.completed":
            raw_usage = event.get("usage")
            if isinstance(raw_usage, dict):
                with contextlib.suppress(TypeError, ValueError):
                    usage = CodexUsage(
                        input_tokens=int(raw_usage.get("input_tokens", 0)),
                        cached_input_tokens=int(raw_usage.get("cached_input_tokens", 0)),
                        output_tokens=int(raw_usage.get("output_tokens", 0)),
                        reasoning_output_tokens=int(raw_usage.get("reasoning_output_tokens", 0)),
                    )

    if last_agent_text is None:
        raise RuntimeError(
            "codex JSONL output contained no agent_message item; "
            "cannot extract model response"
        )

    return CodexInvocationResult(text=last_agent_text, usage=usage)


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

    def _run(
        self,
        prompt: str,
        *,
        output_schema_path: Path | None = None,
    ) -> str:
        result = self.invoker.run(
            prompt,
            timeout_seconds=self.settings.timeout_seconds,
            output_schema_path=output_schema_path,
        )
        return result.text

    @staticmethod
    def _parse_response(raw: str) -> str:
        """Return a JSON string from the model's raw text.

        When schema enforcement is active the model returns clean JSON, so we
        attempt a direct parse first.  If that fails (e.g. the model wrapped
        the output in a code fence despite schema constraints), we fall back to
        the brace-walking ``_extract_json_object`` helper so callers downstream
        always receive a clean JSON string.
        """
        text = raw.strip()
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            return _extract_json_object(raw)

    def infer_dependencies_batched(
        self,
        pairs: Sequence[MarketPair],
    ) -> list[LLMDependencyPrediction]:
        if not pairs:
            return []
        user_prompt = build_batched_dependency_prompt(pairs)
        full_prompt = f"{_BATCHED_SYSTEM_PREAMBLE}\n\n{user_prompt}"
        raw = self._run(full_prompt, output_schema_path=_DEPENDENCY_SCHEMA_PATH)
        json_text = self._parse_response(raw)
        return parse_batched_dependency_predictions(json_text, expected_count=len(pairs))

    def infer_basket_groups(
        self,
        markets: Sequence[MarketDescriptor],
    ) -> list[LLMBasketGroup]:
        if len(markets) < 2:
            return []
        known_ids = frozenset(m.market_id for m in markets)
        user_prompt = build_basket_prompt(markets)
        full_prompt = f"{_BASKET_SYSTEM_PREAMBLE}\n\n{user_prompt}"
        raw = self._run(full_prompt, output_schema_path=_BASKET_SCHEMA_PATH)
        json_text = self._parse_response(raw)
        return parse_llm_basket_groups(json_text, known_market_ids=known_ids)


@dataclass(slots=True)
class SubprocessCodexInvoker(CodexInvoker):
    binary: str = "codex"
    base_args: tuple[str, ...] = ("exec",)
    use_json_flag: bool = True
    extra_env: dict[str, str] = field(default_factory=dict)

    def run(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        output_schema_path: Path | None = None,
    ) -> CodexInvocationResult:
        argv = [self.binary, *self.base_args]
        if self.use_json_flag:
            argv.append("--json")
        if output_schema_path is not None:
            argv.extend(["--output-schema", str(output_schema_path)])

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

        stdout = completed.stdout
        if self.use_json_flag:
            return _parse_jsonl_response(stdout)

        return CodexInvocationResult(text=stdout, usage=None)

    def _build_env(self) -> dict[str, str]:
        import os

        env = dict(os.environ)
        env.update(self.extra_env)
        return env
