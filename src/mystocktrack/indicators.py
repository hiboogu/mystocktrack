"""Pure-python technical indicators over a list of closing prices (oldest first)."""

from __future__ import annotations

import math
from statistics import fmean, pstdev

TRADING_DAYS = 252


def sma(closes: list[float], window: int) -> float | None:
    if len(closes) < window:
        return None
    return fmean(closes[-window:])


def pct_return(closes: list[float], days: int) -> float | None:
    if len(closes) <= days or closes[-days - 1] == 0:
        return None
    return closes[-1] / closes[-days - 1] - 1


def daily_returns(closes: list[float]) -> list[float]:
    return [b / a - 1 for a, b in zip(closes, closes[1:], strict=False) if a]


def annualized_volatility(closes: list[float], days: int = TRADING_DAYS) -> float | None:
    rets = daily_returns(closes[-days - 1 :])
    if len(rets) < 20:
        return None
    return pstdev(rets) * math.sqrt(TRADING_DAYS)


def max_drawdown(closes: list[float], days: int = TRADING_DAYS) -> float | None:
    window = closes[-days:]
    if len(window) < 2:
        return None
    peak, worst = window[0], 0.0
    for price in window:
        peak = max(peak, price)
        worst = max(worst, 1 - price / peak)
    return worst


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None
    changes = [b - a for a, b in zip(closes[-period - 1 : -1], closes[-period:], strict=True)]
    gains = sum(c for c in changes if c > 0) / period
    losses = sum(-c for c in changes if c < 0) / period
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def avg_true_range_pct(closes: list[float], period: int = 14) -> float | None:
    """ATR approximated from closes only, as a fraction of the last price."""
    if len(closes) <= period:
        return None
    moves = [abs(b - a) for a, b in zip(closes[-period - 1 : -1], closes[-period:], strict=True)]
    return fmean(moves) / closes[-1]
