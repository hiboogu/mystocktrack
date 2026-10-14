import pytest
from conftest import FakeLLM

from mystocktrack.agents import PortfolioManager
from mystocktrack.agents.portfolio_manager import allocate
from mystocktrack.report import to_html, to_json, to_markdown


def test_allocate_respects_caps_and_budget():
    w = allocate({"A": 3.0, "B": 1.0, "C": 1.0}, {"A": 0.2, "B": 0.5, "C": 0.5}, budget=0.9)
    assert w["A"] == 0.2
    assert sum(w.values()) == pytest.approx(0.9, abs=1e-3)
    assert w["B"] == w["C"]


def test_allocate_leaves_cash_when_all_capped():
    w = allocate({"A": 1.0, "B": 1.0}, {"A": 0.2, "B": 0.2}, budget=1.0)
    assert sum(w.values()) == pytest.approx(0.4)


def test_full_run_offline(provider, config):
    rec = PortfolioManager(provider, config).run()

    weights = {p.ticker: p.weight for p in rec.long_term}
    assert weights["QUAL"] > 0
    assert weights["JUNK"] == 0
    assert all(w <= config.risk.max_single_weight for w in weights.values())
    crypto = sum(p.weight for p in rec.short_term)
    assert crypto <= config.risk.max_crypto_sleeve + 1e-9
    total = sum(weights.values()) + crypto + rec.cash
    assert total == pytest.approx(1.0, abs=1e-3)
    assert rec.narrative is None

    kinds = [m.kind for m in rec.transcript]
    for kind in ("task", "report", "risk_assessment", "decision"):
        assert kind in kinds
    assert kinds.index("task") < kinds.index("report") < kinds.index("decision")


def test_debate_round_happens_for_risky_bull(provider, config):
    rec = PortfolioManager(provider, config).run()
    challenges = [m for m in rec.transcript if m.kind == "challenge"]
    rebuttals = [m for m in rec.transcript if m.kind == "rebuttal"]
    assert challenges, "high-volatility BTC with a bullish view should be challenged"
    assert len(rebuttals) == len(challenges)
    assert {m.payload["ticker"] for m in challenges} == {m.payload["ticker"] for m in rebuttals}


def test_run_with_llm_adds_narrative(provider, config):
    llm = FakeLLM()
    rec = PortfolioManager(provider, config, llm).run()
    assert rec.narrative == "經理摘要：測試用。"
    md = to_markdown(rec)
    assert "經理摘要" in md and "角色對話紀錄" in md and "不構成任何投資建議" in md


def test_bad_ticker_is_skipped(provider, config):
    config.long_term.append("NOPE")
    rec = PortfolioManager(provider, config).run()
    assert rec.skipped == ["NOPE"]
    assert "NOPE" in to_markdown(rec)
    assert '"skipped"' in to_json(rec)


def test_html_page_escapes_without_markdown_lib(provider, config):
    page = to_html(to_markdown(PortfolioManager(provider, config).run()), "<報告>")
    assert page.startswith("<!doctype html>")
    assert "&lt;報告&gt;" in page


def test_run_fails_when_no_data_at_all(config):
    from mystocktrack.data import StaticDataProvider

    with pytest.raises(RuntimeError, match="no market data"):
        PortfolioManager(StaticDataProvider({}), config).run()
