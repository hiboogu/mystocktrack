"""Historical multiple band, 6-month target price, three scenarios and the rating.

Method (report standard sections 10 and 11):
- P/E when trailing adjusted EPS has been positive through the band period and consensus EPS
  exists; otherwise price/sales on revenue per share. Both are computed when possible so one
  can cross-check the other.
- The band is the stock's own monthly multiples over the last 5 years (20th/50th/80th
  percentile), each month's price divided by the trailing-four-quarter metric known then.
- The 6-month metric is halfway between the trailing figure now and the consensus for the
  next 12 months, i.e. roughly the trailing figure the market will see in six months.
- Base multiple: today's multiple held inside the band's 20th..50th percentile, so the base
  case never assumes the stock re-rates above its own historical median.
- Rating from the base target's 6-month return; speculative holdings are rated 「投機」.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

UNRATED = "未評等"
SPECULATIVE = "投機"
# (minimum 6-month return, rating), checked top-down.
RATING_BANDS = ((0.30, "強力買進"), (0.15, "買進"), (-0.10, "中立"))
DOWNGRADE = "降低持股"
RATING_TABLE = (
    ("強力買進", "> +30%"),
    ("買進", "+15% ～ +30%"),
    ("中立", "−10% ～ +15%"),
    ("降低持股", "< −10%"),
    ("未評等", "資料不足以判斷"),
    ("投機", "投機部位，依部位上限、硬停損、催化劑與檢討日管理"),
)
MIN_BAND_MONTHS = 12
MAX_LOSS_MONTHS = 0.25  # P/E is unsuitable when trailing EPS was negative this often
REPORT_LAG = timedelta(days=75)  # annual figures become known about this long after year end
METHOD_NAMES = {"PE": "本益比", "PS": "股價營收比"}


@dataclass
class Scenario:
    name: str
    multiple: float
    metric: float
    price: float
    upside: float
    trigger: str


@dataclass
class Valuation:
    ticker: str
    rating: str
    method: str | None = None
    method_reason: str = ""
    price: float | None = None
    current_multiple: float | None = None
    band: tuple[float, float, float] | None = None
    band_period: str = ""
    band_months: int = 0
    band_basis: str = ""
    multiple: float | None = None
    multiple_reason: str = ""
    metric_now: float | None = None
    metric_6m: float | None = None
    target: float | None = None
    upside: float | None = None
    scenarios: list[Scenario] = field(default_factory=list)
    cross_check: dict | None = None
    prior: dict | None = None
    note: str = ""


def rating_for(upside: float | None) -> str:
    if upside is None:
        return UNRATED
    for floor, name in RATING_BANDS:
        if upside > floor:
            return name
    return DOWNGRADE


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def ttm_eps(eps_history: list[dict]) -> list[tuple[date, float]]:
    """(announcement date, sum of the last four reported quarters), oldest first."""
    out = []
    for i in range(3, len(eps_history)):
        window = eps_history[i - 3 : i + 1]
        out.append((_d(window[-1]["date"]), sum(q["eps"] for q in window)))
    return out


def annual_series(annual: list[dict], key: str) -> list[tuple[date, float]]:
    """(date the figure became public, value) from newest-first annual rows."""
    out = []
    for r in reversed(annual):
        if r.get(key) is not None and r.get("period"):
            out.append((_d(r["period"]) + REPORT_LAG, r[key]))
    return out


def band_multiples(monthly: list[dict], series: list[tuple[date, float]]):
    """Monthly price / the metric known at that month; returns (multiples, months, losses)."""
    multiples, months, losses = [], [], 0
    for m in monthly:
        day = _d(m["date"])
        known = [v for d, v in series if d <= day]
        if not known:
            continue
        months.append(m["date"][:7])
        if known[-1] > 0:
            multiples.append(m["close"] / known[-1])
        else:
            losses += 1
    return multiples, months, losses


def forward_12m(est: dict, key: str, last_fy_end: date | None, today: date) -> float | None:
    """Next-12-month consensus: the rest of this fiscal year plus the matching part of next."""
    e0 = (est.get("0y") or {}).get(key)
    e1 = (est.get("+1y") or {}).get(key)
    if e0 is None and e1 is None:
        return None
    if e0 is None or e1 is None or last_fy_end is None:
        return e1 if e1 is not None else e0
    next_fy_end = last_fy_end + timedelta(days=365)
    remaining = min(1.0, max(0.0, (next_fy_end - today).days / 365))
    return remaining * e0 + (1 - remaining) * e1


def _pick_multiple(current: float, band: tuple[float, float, float]) -> tuple[float, str]:
    p20, p50, _ = band
    if current > p50:
        return p50, f"目前 {current:.1f} 倍高於歷史中位數，基本情境假設回到中位數 {p50:.1f} 倍"
    if current < p20:
        return p20, f"目前 {current:.1f} 倍低於歷史 20 百分位，基本情境假設回到下緣 {p20:.1f} 倍"
    return current, f"目前 {current:.1f} 倍在歷史區間內，基本情境假設倍數不變，報酬只來自獲利成長"


def _scenarios(base_m, band, metrics, price, label) -> list[Scenario]:
    p20, _, p80 = band
    bull_m = max(base_m, min(p80, base_m * 1.25))
    bear_m = min(base_m * 0.85, max(p20, base_m * 0.7))
    rows = (
        ("悲觀", bear_m, metrics["low"], f"{label}落在共識低標，倍數降到歷史下緣附近"),
        ("基本", base_m, metrics["avg"], f"{label}符合共識，倍數如上"),
        ("樂觀", bull_m, metrics["high"], f"{label}達共識高標，倍數往歷史 80 百分位靠近"),
    )
    out = []
    for name, m, metric, trigger in rows:
        p = m * metric
        out.append(
            Scenario(name, round(m, 2), round(metric, 4), round(p, 2), p / price - 1, trigger)
        )
    return out


def _method(
    kind: str,
    price: float,
    now: float | None,
    fwd: dict,
    series,
    monthly,
    basis: str,
) -> dict | None:
    """Everything for one method, or None when its data is too thin."""
    if not now or now <= 0 or fwd.get("avg") is None or fwd["avg"] <= 0:
        return None
    multiples, months, losses = band_multiples(monthly, series)
    if len(multiples) < MIN_BAND_MONTHS:
        return None
    if kind == "PE" and losses > MAX_LOSS_MONTHS * len(months):
        return None
    band = tuple(round(percentile(multiples, q), 2) for q in (0.2, 0.5, 0.8))
    current = price / now
    base_m, why = _pick_multiple(current, band)
    six = {
        k: 0.5 * now + 0.5 * (fwd.get(k) if fwd.get(k) is not None else fwd["avg"])
        for k in ("low", "avg", "high")
    }
    label = "EPS" if kind == "PE" else "營收"
    scen = _scenarios(base_m, band, six, price, label)
    return {
        "method": kind,
        "current_multiple": round(current, 2),
        "band": band,
        "band_period": f"{months[0]}～{months[-1]}",
        "band_months": len(multiples),
        "band_basis": basis,
        "multiple": round(base_m, 2),
        "multiple_reason": why,
        "metric_now": round(now, 4),
        "metric_6m": round(six["avg"], 4),
        "target": scen[1].price,
        "upside": scen[1].upside,
        "scenarios": scen,
        "losses": losses,
    }


def value(snap, today: date | None = None, speculative: bool = False) -> Valuation:
    """Valuation for one stock snapshot (needs snap.financials from financials.fetch)."""
    today = today or date.today()
    fin = snap.financials or {}
    price = snap.price
    if not fin:
        return Valuation(
            snap.ticker,
            SPECULATIVE if speculative else UNRATED,
            price=price,
            note="沒有財報資料（ETF、指數或 Yahoo 未提供）",
        )
    annual = fin.get("annual") or []
    est = fin.get("estimates") or {}
    monthly = fin.get("monthly_closes") or []
    last_fy = _d(annual[0]["period"]) if annual and annual[0].get("period") else None

    # P/E on Yahoo's adjusted quarterly EPS (the same basis as consensus), else annual GAAP EPS.
    series = ttm_eps(fin.get("eps_history") or [])
    basis = "近四季調整後 EPS"
    if len(series) < 4:
        series, basis = annual_series(annual, "eps"), "年度 EPS"
    eps_now = series[-1][1] if series else None
    eps_fwd = {
        k: forward_12m(est, f"eps{s}", last_fy, today)
        for k, s in (("low", "_low"), ("avg", ""), ("high", "_high"))
    }
    pe = _method("PE", price, eps_now, eps_fwd, series, monthly, basis)

    # Price/sales on revenue per share; shares from the last annual report.
    shares = None
    if annual and annual[0].get("revenue") and annual[0].get("revenue_per_share"):
        shares = annual[0]["revenue"] / annual[0]["revenue_per_share"]
    quarters = [q for q in fin.get("quarters") or [] if q.get("revenue_per_share") is not None]
    rps_now = sum(q["revenue_per_share"] for q in quarters[:4]) if len(quarters) >= 4 else None
    if rps_now is None and annual:
        rps_now = annual[0].get("revenue_per_share")
    rev_fwd = {}
    if shares:
        for k, s in (("low", "_low"), ("avg", ""), ("high", "_high")):
            f = forward_12m(est, f"revenue{s}", last_fy, today)
            rev_fwd[k] = None if f is None else f / shares
    ps = _method(
        "PS",
        price,
        rps_now,
        rev_fwd,
        annual_series(annual, "revenue_per_share"),
        monthly,
        "年度每股營收",
    )

    if pe:
        chosen, other = pe, ps
        reason = f"{basis}在區間內大多為正，獲利可用，採本益比"
    elif ps:
        chosen, other = ps, None
        why = (
            "近四季 EPS 為負或共識 EPS 不足"
            if not eps_now or eps_now <= 0 or not eps_fwd["avg"]
            else "歷史上虧損月份太多，本益比失真"
        )
        reason = f"{why}，改用股價營收比"
    else:
        return Valuation(
            snap.ticker,
            SPECULATIVE if speculative else UNRATED,
            price=price,
            note="歷史倍數或共識預估不足，無法推目標價",
        )

    chosen.pop("losses")
    v = Valuation(
        ticker=snap.ticker,
        rating=SPECULATIVE if speculative else rating_for(chosen["upside"]),
        method_reason=reason,
        price=round(price, 2),
        **chosen,
    )
    if other:
        v.cross_check = {
            "method": other["method"],
            "multiple": other["multiple"],
            "target": other["target"],
            "upside": other["upside"],
        }
    return v


def as_dict(v: Valuation) -> dict:
    return asdict(v)


# --- prior values -----------------------------------------------------------------------
# state/ratings.json: {ticker: {"current": {...}, "previous": {...}}}. A rerun on the same day
# replaces "current" and keeps "previous", so 「前次」 always means the last earlier run.

STATE_FIELDS = ("date", "rating", "target", "price", "upside", "method", "multiple", "metric_6m")


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_state(state: dict, valuations: dict[str, dict], as_of: str) -> dict:
    """Attach each ticker's prior entry to its valuation and return the new state."""
    new = dict(state)
    for t, v in valuations.items():
        entry = state.get(t, {})
        cur = entry.get("current")
        prev = entry.get("previous") if cur and cur.get("date") == as_of else cur
        v["prior"] = prev
        snapshot = {"date": as_of, **{k: v.get(k) for k in STATE_FIELDS if k != "date"}}
        new[t] = {"current": snapshot, "previous": prev}
    return new


def save_state(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
