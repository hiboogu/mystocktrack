"""Short-term trader for bitcoin-related assets: trend, RSI and volatility-based stops."""

from __future__ import annotations

from .. import indicators as ind
from ..data import Snapshot
from .base import AnalystAgent, View, clamp


class CryptoTrader(AnalystAgent):
    name = "crypto_trader"
    title = "比特幣短線交易員"
    persona = (
        "你是比特幣相關資產（BTC、比特幣 ETF、持幣公司）的短線交易員，持有期間數天到數週，"
        "依趨勢、動能與超買超賣給出進出場判斷，並一定附上停損。"
    )

    def rule_view(self, snap: Snapshot, context: dict) -> View:
        c = snap.closes
        score, notes = 0.0, []
        s20, s50 = ind.sma(c, 20), ind.sma(c, 50)
        if s20 and s50:
            up = s20 > s50
            score += 0.3 if up else -0.3
            notes.append("20 日線在 50 日線之上" if up else "20 日線在 50 日線之下")
        if s20:
            score += 0.15 if snap.price > s20 else -0.15
        r = ind.rsi(c, 14)
        if r is not None:
            if r > 70:
                score -= 0.25
                notes.append(f"RSI {r:.0f} 超買")
            elif r < 30:
                score += 0.25
                notes.append(f"RSI {r:.0f} 超賣")
            else:
                notes.append(f"RSI {r:.0f}")
        r1m = ind.pct_return(c, 21)
        if r1m is not None and r1m > 0:
            score += 0.1
        atr = ind.avg_true_range_pct(c, 14) or 0.03
        price = snap.price
        extras = {
            "entry": round(price, 2),
            "stop_loss": round(price * (1 - 2 * atr), 2),
            "take_profit": round(price * (1 + 3 * atr), 2),
        }
        return View(snap.ticker, round(clamp(score), 4), "、".join(notes) + "。", extras)

    @staticmethod
    def signal(score: float) -> str:
        if score >= 0.3:
            return "買進"
        if score <= -0.3:
            return "賣出／觀望"
        return "持有／觀望"
