"""Financial statements, EPS surprises, consensus estimates and the next earnings date.

Yahoo returns these as pandas objects whose shape varies by ticker (ETFs and crypto have
none, Tokyo stocks often lack estimates). Every summarizer here tolerates a missing table or
row and returns plain JSON-able values, so the report can say 「資料不足」 instead of failing.
"""

from __future__ import annotations

import math
from datetime import date, datetime

ANNUAL_YEARS = 3
QUARTERS = 5
SURPRISES = 4
ESTIMATE_PERIODS = {"0q": "本季", "+1q": "下一季", "0y": "本年度", "+1y": "下一年度"}


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _day(x) -> str | None:
    if x is None:
        return None
    if isinstance(x, datetime | date):
        return x.strftime("%Y-%m-%d")
    if hasattr(x, "strftime"):  # pandas Timestamp
        return x.strftime("%Y-%m-%d")
    s = str(x)[:10]
    return s or None


def _empty(df) -> bool:
    return df is None or getattr(df, "empty", True)


def _row(df, *names: str) -> dict:
    """{column: value} for the first row label present, e.g. "Total Revenue"."""
    for name in names:
        if name in df.index:
            return {c: _num(v) for c, v in df.loc[name].items()}
    return {}


def _div(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def _growth(now: float | None, before: float | None) -> float | None:
    return None if now is None or not before or before < 0 else now / before - 1


def statement_rows(
    income, cashflow=None, limit: int = ANNUAL_YEARS, quarterly: bool = False
) -> list[dict]:
    """Newest-first periods with revenue, EPS, revenue per share, margins, FCF and CapEx."""
    if _empty(income):
        return []
    revenue = _row(income, "Total Revenue", "Operating Revenue")
    eps = _row(income, "Diluted EPS", "Basic EPS")
    shares = _row(income, "Diluted Average Shares", "Basic Average Shares")
    gross = _row(income, "Gross Profit")
    op = _row(income, "Operating Income")
    net = _row(income, "Net Income", "Net Income Common Stockholders")
    fcf = capex = {}
    if not _empty(cashflow):
        fcf = _row(cashflow, "Free Cash Flow")
        capex = _row(cashflow, "Capital Expenditure")
    cols = sorted(income.columns, reverse=True)
    rows = []
    for c in cols:
        rev = revenue.get(c)
        if rev is None and eps.get(c) is None:
            continue  # Yahoo pads with an all-empty oldest column
        rows.append(
            {
                "period": _day(c),
                "revenue": rev,
                "eps": eps.get(c),
                "revenue_per_share": _div(rev, shares.get(c)),
                "gross_margin": _div(gross.get(c), rev),
                "operating_margin": _div(op.get(c), rev),
                "net_income": net.get(c),
                "fcf": fcf.get(c),
                "capex": capex.get(c),
            }
        )
    # Year-over-year growth: the same period one step back for annual, four for quarterly.
    step = 4 if quarterly else 1
    for i, r in enumerate(rows):
        prior = rows[i + step] if i + step < len(rows) else {}
        r["revenue_yoy"] = _growth(r["revenue"], prior.get("revenue"))
    return rows[:limit]


def eps_surprises(history, limit: int = SURPRISES) -> list[dict]:
    """Newest-first reported quarters: EPS estimate, actual and surprise (fraction)."""
    if _empty(history):
        return []
    out = []
    for idx, r in history.sort_index(ascending=False).iterrows():
        est, act = _num(r.get("epsEstimate")), _num(r.get("epsActual"))
        if act is None:
            continue
        surprise = _num(r.get("surprisePercent"))
        if surprise is None and est:
            surprise = (act - est) / abs(est)
        out.append({"period": _day(idx), "estimate": est, "actual": act, "surprise": surprise})
    return out[:limit]


def beat_streak(surprises: list[dict]) -> int:
    """Consecutive beats (positive) or misses (negative), counted back from the latest quarter."""
    streak = 0
    for s in surprises:
        x = s.get("surprise")
        if x is None or x == 0:
            break
        if streak == 0:
            streak = 1 if x > 0 else -1
        elif (x > 0) == (streak > 0):
            streak += 1 if streak > 0 else -1
        else:
            break
    return streak


def _period(df, code: str) -> dict:
    if _empty(df) or code not in df.index:
        return {}
    return dict(df.loc[code].items())


def estimates(eps_est, rev_est) -> dict:
    """Consensus for this/next quarter and fiscal year, keyed by Yahoo's period codes."""
    out = {}
    for code in ESTIMATE_PERIODS:
        e = _period(eps_est, code)
        r = _period(rev_est, code)
        row = {
            "eps": _num(e.get("avg")),
            "eps_low": _num(e.get("low")),
            "eps_high": _num(e.get("high")),
            "eps_year_ago": _num(e.get("yearAgoEps")),
            "eps_growth": _num(e.get("growth")),
            "revenue": _num(r.get("avg")),
            "revenue_growth": _num(r.get("growth")),
            "analysts": _num(e.get("numberOfAnalysts")),
        }
        if any(v is not None for v in row.values()):
            out[code] = row
    return out


def next_earnings(calendar, today: date | None = None) -> str | None:
    """The first earnings date on or after today from Yahoo's calendar dict."""
    if not calendar:
        return None
    dates = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
    if not dates:
        return None
    if not isinstance(dates, list | tuple):
        dates = [dates]
    today = today or date.today()
    days = sorted(d for d in (_day(x) for x in dates) if d)
    upcoming = [d for d in days if d >= today.isoformat()]
    return (upcoming or days or [None])[0]


def fetch(ticker_obj, currency: str | None = None) -> dict:
    """Pull everything from a yfinance Ticker; each table is optional."""

    def get(attr):
        try:
            return getattr(ticker_obj, attr)
        except Exception:  # Yahoo endpoints fail independently; keep whatever works.
            return None

    surprises = eps_surprises(get("earnings_history"))
    return {
        "currency": currency,
        "annual": statement_rows(get("income_stmt"), get("cashflow"), ANNUAL_YEARS),
        "quarters": statement_rows(get("quarterly_income_stmt"), None, QUARTERS, quarterly=True),
        "eps_surprises": surprises,
        "beat_streak": beat_streak(surprises),
        "estimates": estimates(get("earnings_estimate"), get("revenue_estimate")),
        "next_earnings": next_earnings(get("calendar")),
    }


def brief(fin: dict) -> dict:
    """The few numbers worth handing to an analyst prompt."""
    if not fin:
        return {}
    last = fin.get("eps_surprises") or [{}]
    est = fin.get("estimates", {})
    return {
        "currency": fin.get("currency"),
        "annual": fin.get("annual", [])[:ANNUAL_YEARS],
        "last_quarter_eps": last[0],
        "beat_streak": fin.get("beat_streak", 0),
        "estimate_this_year": est.get("0y"),
        "estimate_next_year": est.get("+1y"),
        "next_earnings": fin.get("next_earnings"),
    }
