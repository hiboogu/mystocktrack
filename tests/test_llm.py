from types import SimpleNamespace

from mystocktrack.llm import ClaudeLLM, default_llm


class FakeStream:
    def __init__(self, response, sink, kwargs):
        self.response = response
        sink.append(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.response


def make_llm(monkeypatch, response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm = ClaudeLLM()
    calls = []
    llm.client = SimpleNamespace(
        beta=SimpleNamespace(
            messages=SimpleNamespace(stream=lambda **kw: FakeStream(response, calls, kw))
        )
    )
    return llm, calls


def text_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )


def test_json_sends_schema_and_fallback(monkeypatch):
    llm, calls = make_llm(monkeypatch, text_response('{"score": 0.4, "rationale": "ok"}'))
    schema = {"type": "object"}
    assert llm.json("sys", "prompt", schema) == {"score": 0.4, "rationale": "ok"}
    kw = calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert kw["fallbacks"] == "default"


def test_refusal_falls_back_to_rules(monkeypatch):
    llm, _ = make_llm(monkeypatch, text_response("", stop_reason="refusal"))
    assert llm.json("sys", "prompt", {}) is None
    assert llm.text("sys", "prompt") is None


def test_default_llm_needs_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert default_llm() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert default_llm(offline=True) is None
    assert isinstance(default_llm(), ClaudeLLM)
