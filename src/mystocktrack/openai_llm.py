"""OpenAI adapter for the existing LLM protocol."""
import json
import logging
import os

log = logging.getLogger(__name__)

class OpenAILLM:
    def __init__(self, model=None):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model or os.getenv("MYSTOCKTRACK_OPENAI_MODEL", "gpt-5.2")

    def json(self, system, prompt, schema):
        try:
            r = self.client.responses.create(
                model=self.model, instructions=system, input=prompt,
                text={"format": {"type": "json_schema", "name": "agent_result",
                                 "schema": schema, "strict": True}},
            )
            return json.loads(r.output_text)
        except Exception as exc:
            log.warning("GPT JSON call failed; using rules: %s", exc)
            return None

    def text(self, system, prompt):
        try:
            r = self.client.responses.create(
                model=self.model, instructions=system, input=prompt
            )
            return r.output_text or None
        except Exception as exc:
            log.warning("GPT text call failed; skipping narrative: %s", exc)
            return None


def default_openai_llm(offline=False):
    if offline or not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAILLM()
