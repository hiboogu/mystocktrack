from datetime import date

import pandas as pd

from mystocktrack import financials as fin
from mystocktrack.agents import PortfolioManager
from mystocktrack.agents.fundamentals import FundamentalsAnalyst
from mystocktrack.bus import MessageBus
from mystocktrack.data import Snapshot
from mystocktrack.report import to_markdown

YEARS = [pd.Timestamp(f"{y}-12-31") for y in (2025, 2024, 2023, 2022)]


def income():
    return pd.DataFrame(
        {
            YEARS[0]: [1200e6, 600e6, 300e6, 240e6, 2.4, 100e6],
            YEARS[1]: [1000e6, 480e6, 220e6, 180e6, 1.8, 100e6],
            YEARS[2]: [800e6, 380e6, 150e6, 120e6, 1.2, 100e6],
            YEARS[3]: [float("nan")] * 6,  # Yahoo pads the oldest column
        },
        index=[
            "Total Revenue",
            "Gross Profit",
            "Operating Income",
            "Net Income",
            "Diluted EPS",
            "Diluted Average Shares",
        ],
    )


def cashflow():
    return pd.DataFrame(
        {YEARS[0]: [200e6, -50e6], YEARS[1]: [150e6, -40e6], YEARS[2]: [90e6, -30e6]},
        index=["Free Cash Flow", "Capital Expenditure"],
    )


def history():
    idx = pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"])
    return pd.DataFrame(
        {
            "epsEstimate": [0.50, 0.55, 0.60, 0.62],
            "epsActual": [0.45, 0.58, 0.63, 0.66],
            "surprisePercent": [-0.10, 0.0545, 0.05, 0.0645],
        },
        index=idx,
    )


def eps_estimate():
    return pd.DataFrame(
        {
            "avg": [0.70, 0.75, 2.8, 3.4],
            "low": [0.6, 0.6, 2.5, 3.0],
            "high": [0.8, 0.9, 3.0, 3.9],
            "yearAgoEps": [0.5, 0.55, 2.4, 2.8],
            "numberOfAnalysts": [20, 18, 25, 22],
            "growth": [0.4, 0.36, 0.17, 0.21],
        },
        index=["0q", "+1q", "0y", "+1y"],
    )


def revenue_estimate():
    return pd.DataFrame(
        {"avg": [350e6, 370e6, 1400e6, 1650e6], "growth": [0.3, 0.28, 0.17, 0.18]},
        index=["0q", "+1q", "0y", "+1y"],
    )


class FakeTicker:
    income_stmt = income()
    cashflow = cashflow()
    quarterly_income_stmt = pd.DataFrame()
    earnings_history = history()
    earnings_estimate = eps_estimate()
    revenue_estimate = revenue_estimate()
    calendar = {"Earnings Date": [date(2099, 2, 1)], "Earnings Average": 0.7}


class BrokenTicker:
    def __getattr__(self, name):
        raise RuntimeError("Yahoo said no")


def test_statement_rows_newest_first_with_per_share_and_growth():
    rows = fin.statement_rows(income(), cashflow())
    assert [r["period"] for r in rows] == ["2025-12-31", "2024-12-31", "2023-12-31"]
    top = rows[0]
    assert top["revenue_per_share"] == 12.0
    assert top["eps"] == 2.4
    assert top["fcf"] == 200e6 and top["capex"] == -50e6
    assert round(top["revenue_yoy"], 4) == 0.2
    assert top["gross_margin"] == 0.5
    assert rows[-1]["revenue_yoy"] is None  # padded column is dropped, no prior year


def test_surprises_and_streak():
    s = fin.eps_surprises(history())
    assert s[0]["period"] == "2025-12-31" and s[0]["actual"] == 0.66
    assert fin.beat_streak(s) == 3
    assert fin.beat_streak([{"surprise": -0.1}, {"surprise": -0.2}, {"surprise": 0.1}]) == -2
    assert fin.beat_streak([]) == 0


def test_estimates_and_next_earnings():
    e = fin.estimates(eps_estimate(), revenue_estimate())
    assert e["+1y"]["eps"] == 3.4 and e["+1y"]["revenue"] == 1650e6
    assert e["0q"]["analysts"] == 20
    assert fin.estimates(None, None) == {}
    cal = {"Earnings Date": [date(2020, 1, 1), date(2026, 11, 18)]}
    assert fin.next_earnings(cal, today=date(2026, 10, 19)) == "2026-11-18"
    assert fin.next_earnings({}, today=date(2026, 10, 19)) is None
    past = {"Earnings Date": [date(2026, 8, 21)]}
    assert fin.next_earnings(past, today=date(2026, 10, 19)) is None


def test_revenue_growth_recomputed_from_reported_year():
    annual = fin.statement_rows(income(), cashflow())
    e = fin.estimates(eps_estimate(), revenue_estimate(), annual)
    assert round(e["0y"]["revenue_growth"], 4) == round(1400 / 1200 - 1, 4)
    assert round(e["+1y"]["revenue_growth"], 4) == round(1650 / 1400 - 1, 4)
    assert e["0q"]["revenue_growth"] == 0.3  # quarters keep Yahoo's figure


def test_fetch_survives_missing_endpoints():
    full = fin.fetch(FakeTicker(), "USD")
    assert full["beat_streak"] == 3 and full["next_earnings"] == "2099-02-01"
    assert len(full["annual"]) == 3 and full["quarters"] == []
    empty = fin.fetch(BrokenTicker(), "USD")
    assert empty["annual"] == [] and empty["estimates"] == {} and empty["next_earnings"] is None


def test_fundamentals_rewards_beats_and_growth(snapshots):
    snap = snapshots["QUAL"]
    agent = FundamentalsAnalyst(MessageBus())
    plain = agent.rule_view(snap, {})
    rich = Snapshot(snap.ticker, snap.closes, snap.fundamentals, fin.fetch(FakeTicker(), "USD"))
    boosted = agent.rule_view(rich, {})
    assert boosted.score > plain.score
    assert "連續 3 季 EPS 優於共識" in boosted.rationale


def test_report_shows_earnings_and_marks_missing(snapshots, config, provider):
    snapshots["QUAL"].financials = fin.fetch(FakeTicker(), "USD")
    md = to_markdown(PortfolioManager(provider, config).run())
    assert "## 財報與預期" in md
    assert "| 2025-12-31 | 1,200 | +20.0% | 12.00 | 2.40 | 200 | -50 |" in md
    assert "EPS 實際 0.66，共識 0.62，差異 +6.5%；連續 3 季優於共識" in md
    assert "共識下一年度：EPS 3.40（YoY +21.0%），營收 1,650（百萬美元，YoY +17.9%）" in md
    assert "下次財報日：2099-02-01" in md
    assert "### JUNK\n\n資料不足" in md
