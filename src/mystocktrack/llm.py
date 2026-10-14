"""Claude access for the agents. Without ANTHROPIC_API_KEY the agents run on their rule-based logic."""

from __future__ import annotations

import json
import logging
import os
from typing import Protocol

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"


class LLM(Protocol):
    def json(self, system: str, prompt: str, schema: dict) -> dict | None: ...

    def text(self, system: str, prompt: str) -> str | None: ...


class ClaudeLLM:
    def __init__(self, model: str | None = None, effort: str = "medium"):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("MYSTOCKTRACK_MODEL", DEFAULT_MODEL)
        self.effort = effort

    def _create(self, system: str, prompt: str, output_config: dict):
        # fallbacks="default" retries a safety-classifier decline on Anthropic's recommended model.
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=32000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("Claude stopped with %s; using rule-based result", response.stop_reason)
            return None
        return "".join(b.text for b in response.content if b.type == "text")

    def json(self, system: str, prompt: str, schema: dict) -> dict | None:
        try:
            text = self._create(
                system,
                prompt,
                {"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            )
            return json.loads(text) if text else None
        except (self._anthropic.APIError, json.JSONDecodeError) as exc:
            log.warning("Claude call failed (%s); using rule-based result", exc)
            return None

    def text(self, system: str, prompt: str) -> str | None:
        try:
            return self._create(system, prompt, {"effort": self.effort})
        except self._anthropic.APIError as exc:
            log.warning("Claude call failed (%s); skipping narrative", exc)
            return None


def default_llm(offline: bool = False) -> LLM | None:
    if offline or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return ClaudeLLM()
