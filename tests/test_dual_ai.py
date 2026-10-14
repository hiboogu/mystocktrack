"""Tests use synthetic market data and mock API calls."""
import json
import sys
from types import SimpleNamespace

from mystocktrack.agents import PortfolioManager
from mystocktrack.data import StaticDataProvider
from mystocktrack.openai_llm import OpenAILLM, default_openai_llm
from mystocktrack.shared_snapshot import capture, load_snapshot, save_snapshot


def test_same_snapshot(config, snapshots, tmp_path):
    class CountProvider(StaticDataProvider):
        def __init__(self, data):
            super().__init__(data)
            self.calls = []

        def snapshot(self, ticker):
            self.calls.append(ticker)
            return super().snapshot(ticker)

    provider = CountProvider(snapshots)
    shared, frozen = capture(config, provider)
    assert len(provider.calls) == len(set(provider.calls))
    filepath = tmp_path / "snapshot.json"
    save_snapshot(frozen, filepath)
    restored = load_snapshot(filepath)
    assert restored.snapshot("QUAL").closes == shared.snapshot("QUAL").closes
    a = PortfolioManager(restored, config).run()
    b = PortfolioManager(restored, config).run()
    assert [(x.ticker, x.score) for x in a.long_term] == [
        (x.ticker, x.score) for x in b.long_term
    ]


def test_openai_adapter(monkeypatch):
    calls = []
    class Client:
        def __init__(self):
            self.responses = SimpleNamespace(create=self.create)
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text='{"views":[]}')
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    assert OpenAILLM("test-model").json("s", "p", {"type": "object"}) == {"views": []}
    assert calls[0]["model"] == "test-model"


def test_api_key_optional(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert default_openai_llm() is None
