from dataclasses import replace

from conftest import series

from mystocktrack.agents import MacroSentimentAnalyst, PortfolioManager
from mystocktrack.agents.macro_sentiment import japan_regime
from mystocktrack.bus import MessageBus
from mystocktrack.data import Snapshot, StaticDataProvider, currency_of, market_of
from mystocktrack.report import label, to_markdown


def rising(start: float, step: float, days: int = 280) -> list[float]:
    return [start * (1 + step * i) for i in range(days)]


def japan_snaps():
    # Steady Nikkei uptrend; the yen weakens about 10% over the last three months.
    return {
        "^N225": Snapshot("^N225", rising(38000, 0.001), {}),
        "JPY=X": Snapshot("JPY=X", rising(130, 0.0015), {}),
        "6920.T": Snapshot("6920.T", series(20000, 0.0008, 0.020, seed=13), {}),
    }


def test_market_and_currency_from_ticker():
    assert market_of("6920.T") == "JP" and currency_of("6861.T") == "JPY"
    assert market_of("NVDA") == "US" and currency_of("NVDA") == "USD"


def test_japan_regime_notes_weak_yen():
    snaps = japan_snaps()
    score, notes = japan_regime({"nikkei": snaps["^N225"], "usdjpy": snaps["JPY=X"]})
    assert score > 0
    assert any("日圓三個月內走弱" in n for n in notes)


def test_macro_uses_japan_backdrop_for_tokyo_stocks(snapshots):
    agent = MacroSentimentAnalyst(MessageBus())
    context = {"regime_notes": ["S&P 500 在 200 日均線之上"], "japan_regime_notes": ["日經 X"]}
    jp = agent.rule_view(japan_snaps()["6920.T"], context)
    us = agent.rule_view(snapshots["QUAL"], context)
    assert "日經" in jp.rationale and "S&P" not in jp.rationale
    assert "S&P" in us.rationale


def test_run_with_tokyo_stock(snapshots, config):
    provider = StaticDataProvider({**snapshots, **japan_snaps()})
    cfg = replace(config, long_term=[*config.long_term, "6920.T"], names={"6920.T": "Lasertec"})
    rec = PortfolioManager(provider, cfg).run()
    assert "6920.T" in {p.ticker for p in rec.long_term}
    assert any(n.startswith("日本：") for n in rec.regime_notes)
    assert "6920.T（Lasertec，日股，日圓計價）" in to_markdown(rec)


def test_us_only_run_skips_japan_data(snapshots, config):
    rec = PortfolioManager(StaticDataProvider(snapshots), config).run()
    assert not any(n.startswith("日本：") for n in rec.regime_notes)
    assert label("NVDA", {}) == "NVDA"
