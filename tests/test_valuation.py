from datetime import date

from mystocktrack import valuation as val
from mystocktrack.agents import PortfolioManager
from mystocktrack.data import Snapshot
from mystocktrack.report import to_markdown

TODAY = date(2026, 10, 19)


def months(n=60, start=(2021, 11)):
    y, m = start
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}-01")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def quarters(eps_values, start=(2020, 2)):
    y, m = start
    out = []
    for e in eps_values:
        out.append({"date": f"{y}-{m:02d}-15", "eps": e})
        y, m = (y + 1, m - 9) if m > 9 else (y, m + 3)
    return out


def financials(eps_values, pe=20.0, revenue_ps=10.0, est_eps=(10.0, 11.0), shares=100.0):
    hist = quarters(eps_values)
    series = val.ttm_eps(hist)
    closes = []
    for d in months():
        known = [v for day, v in series if day <= date.fromisoformat(d)]
        closes.append({"date": d, "close": pe * known[-1] if known and known[-1] > 0 else 50.0})
    annual = [
        {
            "period": f"{y}-12-31",
            "revenue": revenue_ps * shares,
            "revenue_per_share": revenue_ps,
            "eps": 1.0,
        }
        for y in (2025, 2024, 2023, 2022)
    ]
    e0, e1 = est_eps
    return {
        "currency": "USD",
        "annual": annual,
        "quarters": [],
        "eps_history": hist,
        "monthly_closes": closes,
        "estimates": {
            "0y": {"eps": e0, "eps_low": e0 * 0.9, "eps_high": e0 * 1.1, "revenue": 1100.0},
            "+1y": {"eps": e1, "eps_low": e1 * 0.9, "eps_high": e1 * 1.1, "revenue": 1200.0},
        },
    }


def snap(price, fin, ticker="TEST"):
    return Snapshot(ticker, [price] * 260, {"quoteType": "EQUITY"}, fin)


def test_rating_bands():
    assert val.rating_for(0.31) == "強力買進"
    assert val.rating_for(0.20) == "買進"
    assert val.rating_for(0.0) == "中立"
    assert val.rating_for(-0.11) == "降低持股"
    assert val.rating_for(None) == "未評等"


def test_pe_band_target_and_scenarios():
    fin = financials([1.0 + 0.05 * i for i in range(27)])
    ttm_now = sum(q["eps"] for q in fin["eps_history"][-4:])
    v = val.value(snap(20.0 * ttm_now, fin), TODAY)
    assert v.method == "PE"
    assert v.band_months >= 50
    assert 19.0 < v.band[1] < 21.0  # the stock always traded near 20x trailing EPS
    assert abs(v.current_multiple - 20.0) < 0.01
    assert v.target > v.price  # consensus EPS is above the trailing figure
    assert [s.name for s in v.scenarios] == ["悲觀", "基本", "樂觀"]
    bear, base, bull = (s.price for s in v.scenarios)
    assert bear < base < bull and base == v.target
    assert v.rating == val.rating_for(v.upside)


def test_expensive_stock_reverts_to_median_and_is_downgraded():
    fin = financials([1.0] * 27, est_eps=(4.0, 4.0))
    v = val.value(snap(200.0, fin), TODAY)  # 50x against a 20x history
    assert v.multiple == v.band[1]
    assert v.rating == "降低持股"


def test_loss_maker_falls_back_to_price_sales():
    fin = financials([-0.5] * 27, est_eps=(-1.0, -0.5))
    v = val.value(snap(30.0, fin), TODAY)
    assert v.method == "PS"
    assert "股價營收比" in v.method_reason
    assert v.cross_check is None


def test_speculative_and_missing_data():
    fin = financials([1.0 + 0.05 * i for i in range(27)])
    assert val.value(snap(30.0, fin), TODAY, speculative=True).rating == "投機"
    assert val.value(snap(30.0, {}), TODAY).rating == "未評等"
    thin = {**fin, "monthly_closes": fin["monthly_closes"][-6:]}
    assert val.value(snap(30.0, thin), TODAY).rating == "未評等"


def test_state_keeps_previous_run_across_same_day_reruns():
    state = {}
    first = {"T": {"rating": "買進", "target": 120.0, "price": 100.0}}
    state = val.update_state(state, first, "2026-10-19")
    assert first["T"]["prior"] is None
    second = {"T": {"rating": "中立", "target": 110.0, "price": 105.0}}
    state = val.update_state(state, second, "2026-10-20")
    assert second["T"]["prior"]["rating"] == "買進"
    rerun = {"T": {"rating": "強力買進", "target": 150.0, "price": 105.0}}
    state = val.update_state(state, rerun, "2026-10-20")
    assert rerun["T"]["prior"]["date"] == "2026-10-19"
    assert state["T"]["current"]["rating"] == "強力買進"


def test_state_roundtrip(tmp_path):
    path = tmp_path / "state" / "ratings.json"
    assert val.load_state(path) == {}
    val.save_state(path, {"T": {"current": {"rating": "買進"}}})
    assert val.load_state(path)["T"]["current"]["rating"] == "買進"


def test_report_has_ratings_table(snapshots, config, provider):
    fin = financials([1.0 + 0.05 * i for i in range(27)])
    snapshots["QUAL"].financials = fin
    rec = PortfolioManager(provider, config).run()
    md = to_markdown(rec)
    assert "## 評等與目標價（6 個月）" in md
    assert "強力買進 > +30%" in md
    assert rec.valuations["QUAL"]["method"] == "PE"
    assert "- 估值方法：本益比" in md
    assert "目標價 ＝" in md
    assert rec.valuations["JUNK"]["rating"] == "未評等"
