import pytest

from mystocktrack.agents import PortfolioManager
from mystocktrack.agents.portfolio_manager import holding_action
from mystocktrack.config import load_config
from mystocktrack.report import to_markdown


def test_holding_action_rules():
    assert holding_action(0.5, 0.1, 0.3) == "可加碼"
    assert holding_action(0.2, -0.1, 0.3) == "續抱"
    assert holding_action(0.0, 0.2, 0.3) == "減碼"
    assert holding_action(-0.5, 0.2, 0.3) == "獲利了結"
    assert holding_action(-0.5, -0.2, 0.3) == "停損出場"
    # Deep loss and the team is not bullish: cut it even with a mildly positive score.
    assert holding_action(0.2, -0.4, 0.3) == "停損出場"
    # Deep loss but the team is bullish: keep it.
    assert holding_action(0.5, -0.4, 0.3) == "可加碼"


def test_load_config_reads_holdings_and_adds_them_to_analysis(tmp_path):
    path = tmp_path / "w.toml"
    path.write_text(
        '[long_term]\ntickers = ["NVDA"]\n[short_term]\ntickers = ["MSTR"]\n'
        "[holdings]\nKBR = { cost = 38.1, shares = 20 }\nMSTR = { cost = 126.3, shares = 2 }\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.holdings["KBR"].shares == 20
    assert cfg.long_term == ["NVDA", "KBR"]  # held but unlisted -> long term
    assert cfg.short_term == ["MSTR"]  # already listed short term, not duplicated


def test_repo_watchlist_parses():
    cfg = load_config("watchlist.toml")
    assert set(cfg.holdings) <= set(cfg.long_term) | set(cfg.short_term)


def test_run_reviews_each_holding(provider, held_config):
    rec = PortfolioManager(provider, held_config).run()
    by_ticker = {h.ticker: h for h in rec.holdings}
    assert set(by_ticker) == {"QUAL", "JUNK", "MSTR"}

    junk = by_ticker["JUNK"]
    assert junk.pnl < 0 and junk.action == "停損出場"
    qual = by_ticker["QUAL"]
    assert qual.value == pytest.approx(qual.price * 10, abs=0.1)
    assert qual.pnl == pytest.approx(qual.value - 500.0, abs=0.01)
    assert by_ticker["MSTR"].stop_price is not None

    md = to_markdown(rec)
    assert "我的持股檢視" in md and "停損出場" in md
    long_actions = {p.ticker: p.action for p in rec.long_term}
    assert long_actions["QUAL"] == "已持有（見持股檢視）"
    assert long_actions["VOO"] != "已持有（見持股檢視）"


def test_holdings_reach_the_narrative(provider, held_config):
    from conftest import FakeLLM

    llm = FakeLLM()
    PortfolioManager(provider, held_config, llm).run()
    narrative_prompt = llm.calls[-1][1]
    assert '"holdings"' in narrative_prompt and "JUNK" in narrative_prompt
