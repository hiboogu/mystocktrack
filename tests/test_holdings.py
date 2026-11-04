import pytest

from mystocktrack.agents import PortfolioManager
from mystocktrack.agents.portfolio_manager import holding_action
from mystocktrack.config import load_config
from mystocktrack.report import to_markdown


def test_holding_action_rules():
    assert holding_action(0.5, 100.0, 90.0) == "可加碼"
    assert holding_action(0.2, 100.0, 90.0) == "續抱"
    assert holding_action(0.0, 100.0, 90.0) == "減碼"
    assert holding_action(-0.5, 100.0, 90.0) == "出場"
    # Below the stop line: out, whatever the team thinks.
    assert holding_action(0.5, 89.0, 90.0) == "停損出場"
    assert holding_action(0.2, 100.0, None) == "續抱"


def test_cost_does_not_change_the_decision(provider, held_config):
    """Same price, same outlook: the answer must not depend on what the user paid."""
    from dataclasses import replace

    from mystocktrack.config import Holding

    actions = []
    for cost in (1.0, 50.0, 10_000.0):
        holdings = {"QUAL": Holding(cost, 10), "JUNK": Holding(cost, 5)}
        rec = PortfolioManager(provider, replace(held_config, holdings=holdings)).run()
        actions.append({h.ticker: (h.action, h.stop_price) for h in rec.holdings})
    assert actions[0] == actions[1] == actions[2]


def test_old_cost_based_risk_keys_are_ignored(tmp_path):
    path = tmp_path / "w.toml"
    path.write_text(
        "[risk]\nmax_loss_from_cost = 0.3\nspeculative_max_loss = 0.5\nmax_single_weight = 0.25\n",
        encoding="utf-8",
    )
    assert load_config(path).risk.max_single_weight == 0.25


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
    assert junk.pnl < 0 and junk.action == "出場"
    qual = by_ticker["QUAL"]
    assert qual.value == pytest.approx(qual.price * 10, abs=0.1)
    assert qual.pnl == pytest.approx(qual.value - 500.0, abs=0.01)
    assert by_ticker["MSTR"].stop_price is not None

    md = to_markdown(rec)
    assert "我的持股檢視" in md and "出場" in md
    long_actions = {p.ticker: p.action for p in rec.long_term}
    assert long_actions["QUAL"] == "已持有（見持股檢視）"
    assert long_actions["VOO"] != "已持有（見持股檢視）"


def test_holdings_reach_the_narrative(provider, held_config):
    from conftest import FakeLLM

    llm = FakeLLM()
    PortfolioManager(provider, held_config, llm).run()
    narrative_prompt = llm.calls[-1][1]
    assert '"holdings"' in narrative_prompt and "JUNK" in narrative_prompt


def test_speculative_action_rules():
    from mystocktrack.agents.portfolio_manager import speculative_action
    from mystocktrack.config import RiskLimits

    risk = RiskLimits(speculative_max_weight=0.05)
    assert speculative_action(1.9, 2.0, 0.02, risk, "", "2026-10-14") == "停損出場（跌破停損）"
    assert (
        speculative_action(2.5, 2.0, 0.02, risk, "2026-06-30", "2026-10-14")
        == "催化劑到期，重新檢討"
    )
    assert (
        speculative_action(2.5, 2.0, 0.12, risk, "2027-06-30", "2026-10-14")
        == "投機持有，減碼至 5%"
    )
    assert speculative_action(2.5, None, 0.03, risk, "", "2026-10-14") == "投機持有"


def test_speculative_holding_ignores_long_term_exit(provider, held_config, snapshots):
    from dataclasses import replace

    from mystocktrack.config import Holding

    cost = snapshots["JUNK"].price * 1.05  # a small loss
    holdings = {**held_config.holdings, "JUNK": Holding(cost, 5, speculative=True, catalyst="新品")}
    rec = PortfolioManager(provider, replace(held_config, holdings=holdings)).run()
    junk = {h.ticker: h for h in rec.holdings}["JUNK"]
    assert junk.score < 0  # the team is still bearish
    assert junk.action.startswith("投機持有")
    assert junk.stop_price is not None and junk.stop_price < snapshots["JUNK"].price
    assert sum(h.weight for h in rec.holdings) == pytest.approx(1.0, abs=0.001)
    md = to_markdown(rec)
    assert "JUNK（投機）" in md and "催化劑：新品" in md


def test_category_and_agreed_stop(provider, held_config):
    from dataclasses import replace

    from mystocktrack.config import Holding

    holdings = {
        "QUAL": Holding(50.0, 10, category="長期", stop=42.5),
        "JUNK": Holding(200.0, 5, category="投機"),
        "MSTR": Holding(100.0, 2, category="短線"),
    }
    rec = PortfolioManager(provider, replace(held_config, holdings=holdings)).run()
    by_ticker = {h.ticker: h for h in rec.holdings}
    assert by_ticker["QUAL"].stop_price == 42.5  # agreed stop replaces the computed one
    assert by_ticker["JUNK"].speculative  # 投機 implies speculative rules
    md = to_markdown(rec)
    assert "QUAL（長期）" in md and "MSTR（短線）" in md and "分類占比：" in md
