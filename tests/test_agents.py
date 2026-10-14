import pytest
from conftest import FakeLLM

from mystocktrack.agents import CryptoTrader, FundamentalsAnalyst, MacroSentimentAnalyst
from mystocktrack.agents.macro_sentiment import market_regime
from mystocktrack.bus import MessageBus


def test_fundamentals_prefers_quality(snapshots):
    agent = FundamentalsAnalyst(MessageBus())
    good = agent.rule_view(snapshots["QUAL"], {})
    bad = agent.rule_view(snapshots["JUNK"], {})
    etf = agent.rule_view(snapshots["VOO"], {})
    assert good.stance == "看多"
    assert bad.stance == "看空"
    assert etf.score > 0


def test_market_regime_calm_uptrend(snapshots):
    score, notes = market_regime(
        {"spx": snapshots["^GSPC"], "vix": snapshots["^VIX"], "tnx": snapshots["^TNX"]}
    )
    assert score > 0
    assert any("VIX" in n for n in notes)


def test_macro_follows_momentum(snapshots):
    agent = MacroSentimentAnalyst(MessageBus())
    assert (
        agent.rule_view(snapshots["QUAL"], {}).score > agent.rule_view(snapshots["JUNK"], {}).score
    )


def test_crypto_trader_sets_stops(snapshots):
    view = CryptoTrader(MessageBus()).rule_view(snapshots["BTC-USD"], {})
    e = view.extras
    assert e["stop_loss"] < e["entry"] < e["take_profit"]


def test_analyze_reports_to_lead(snapshots):
    bus = MessageBus()
    FundamentalsAnalyst(bus).analyze({"QUAL": snapshots["QUAL"]}, {}, "portfolio_manager")
    reports = bus.inbox("portfolio_manager", "report")
    assert len(reports) == 1 and reports[0].sender == "fundamentals"


def test_llm_refines_draft(snapshots):
    llm = FakeLLM(bump=0.1)
    agent = FundamentalsAnalyst(MessageBus(), llm)
    rule = agent.rule_view(snapshots["JUNK"], {}).score
    views = agent.analyze({"JUNK": snapshots["JUNK"]}, {}, "pm")
    assert views["JUNK"].score == pytest.approx(rule + 0.1)
    assert views["JUNK"].rationale == "LLM 修正"
    assert "基本面" in llm.calls[0][0]


def test_challenge_lowers_conviction_without_llm(snapshots):
    bus = MessageBus()
    agent = CryptoTrader(bus)
    agent.analyze({"MSTR": snapshots["MSTR"]}, {}, "pm")
    before = agent.views["MSTR"].score
    after = agent.respond_to_challenge("MSTR", "太波動", snapshots["MSTR"], "pm")
    assert before > 0
    assert after.revised and after.score < before
    assert bus.inbox("risk_manager", "rebuttal")
