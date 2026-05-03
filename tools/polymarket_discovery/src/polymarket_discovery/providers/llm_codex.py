from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from ..contracts import MarketDescriptor
from ..interfaces.codex_invoker import CodexInvoker
from ..interfaces.llm_dependency_prediction import LLMDependencyPrediction
from ..interfaces.llm_provider import LLMProvider
from .llm_codec import build_dependency_prompt, parse_llm_dependency_prediction
from .settings import LLMProviderSettings


_SYSTEM_PREAMBLE = (
    "You infer market dependencies. Reply with a single JSON object containing "
    "edge_type, confidence, rationale. edge_type must be one of "
    "mutually_exclusive, conditional, related. confidence must be a number from "
    "0 to 1. Do not wrap the JSON in code fences or include any other text."
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

    def infer_dependency(
        self,
        left_market: MarketDescriptor,
        right_market: MarketDescriptor,
    ) -> LLMDependencyPrediction:
        user_prompt = build_dependency_prompt(left_market, right_market)
        full_prompt = f"{_SYSTEM_PREAMBLE}\n\n{user_prompt}"
        raw = self.invoker.run(full_prompt, timeout_seconds=self.settings.timeout_seconds)
        json_text = _extract_json_object(raw)
        return parse_llm_dependency_prediction(json_text)


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
