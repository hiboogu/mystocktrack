"""Market data snapshots. Yahoo Finance in production, static snapshots in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from . import indicators as ind

MACRO_TICKERS = {"spx": "^GSPC", "vix": "^VIX", "tnx": "^TNX"}

FUNDAMENTAL_FIELDS = (
    "trailingPE",
    "forwardPE",
    "pegRatio",
    "priceToBook",
    "profitMargins",
    "returnOnEquity",
    "revenueGrowth",
    "earningsGrowth",
    "debtToEquity",
    "freeCashflow",
    "marketCap",
    "dividendYield",
    "quoteType",
)


@dataclass
class Snapshot:
    ticker: str
    closes: list[float]
    fundamentals: dict = field(default_factory=dict)

    @property
    def price(self) -> float:
        return self.closes[-1]

    def metrics(self) -> dict:
        c = self.closes
        return {
            "price": round(self.price, 2),
            "return_1m": _r(ind.pct_return(c, 21)),
            "return_6m": _r(ind.pct_return(c, 126)),
            "return_12m": _r(ind.pct_return(c, 252)),
            "sma20": _r(ind.sma(c, 20)),
            "sma50": _r(ind.sma(c, 50)),
            "sma200": _r(ind.sma(c, 200)),
            "rsi14": _r(ind.rsi(c, 14)),
            "atr_pct": _r(ind.avg_true_range_pct(c, 14)),
            "volatility_1y": _r(ind.annualized_volatility(c)),
            "max_drawdown_1y": _r(ind.max_drawdown(c)),
        }


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


class DataProvider(Protocol):
    def snapshot(self, ticker: str) -> Snapshot: ...


class StaticDataProvider:
    """Serves pre-built snapshots; used by tests and offline demos."""

    def __init__(self, snapshots: dict[str, Snapshot]):
        self._snapshots = snapshots

    def snapshot(self, ticker: str) -> Snapshot:
        return self._snapshots[ticker]


class YahooDataProvider:
    """Daily closes (about 13 months) and key fundamentals from Yahoo Finance via yfinance."""

    def __init__(self, period: str = "13mo"):
        self.period = period

    def snapshot(self, ticker: str) -> Snapshot:
        import yfinance as yf

        t = yf.Ticker(ticker)
        hist = t.history(period=self.period, interval="1d", auto_adjust=True)
        closes = [float(x) for x in hist["Close"].dropna().tolist()]
        if not closes:
            raise ValueError(f"no price history for {ticker}")
        try:
            info = t.info or {}
        except Exception:  # Yahoo's info endpoint is flaky; prices alone still work.
            info = {}
        return Snapshot(ticker, closes, {k: info.get(k) for k in FUNDAMENTAL_FIELDS})
