"""Long-term fundamentals and valuation analyst for US stocks (value + quality lens)."""

from __future__ import annotations

from ..data import Snapshot
from .base import AnalystAgent, View, clamp


class FundamentalsAnalyst(AnalystAgent):
    name = "fundamentals"
    title = "基本面／估值分析師"
    persona = (
        "你是美股長期投資的基本面與估值分析師，結合價值投資（安全邊際、合理本益比）"
        "與品質投資（高 ROE、穩定現金流、低負債）的觀點，評估是否值得持有 5 年以上。"
    )

    def evidence(self, snap: Snapshot) -> dict:
        return {"ticker": snap.ticker, "fundamentals": snap.fundamentals, "metrics": snap.metrics()}

    def rule_view(self, snap: Snapshot, context: dict) -> View:
        f = snap.fundamentals
        if f.get("quoteType") == "ETF":
            return View(snap.ticker, 0.35, "指數型 ETF，分散且費用低，適合當長期核心部位。")

        score, notes = 0.0, []

        def add(points: float, note: str) -> None:
            nonlocal score
            score += points
            notes.append(note)

        pe = f.get("forwardPE") or f.get("trailingPE")
        if pe is not None:
            if pe <= 0:
                add(-0.3, "獲利為負")
            elif pe < 15:
                add(0.3, f"本益比 {pe:.1f} 偏低")
            elif pe < 25:
                add(0.1, f"本益比 {pe:.1f} 合理")
            elif pe > 40:
                add(-0.3, f"本益比 {pe:.1f} 偏高")
        peg = f.get("pegRatio")
        if peg is not None and peg > 0:
            if peg < 1.5:
                add(0.2, f"PEG {peg:.2f} 具成長性價比")
            elif peg > 3:
                add(-0.2, f"PEG {peg:.2f} 偏貴")
        roe = f.get("returnOnEquity")
        if roe is not None and roe > 0.15:
            add(0.2, f"ROE {roe:.0%}")
        margin = f.get("profitMargins")
        if margin is not None and margin > 0.15:
            add(0.15, f"淨利率 {margin:.0%}")
        growth = f.get("revenueGrowth")
        if growth is not None:
            if growth > 0.10:
                add(0.15, f"營收成長 {growth:.0%}")
            elif growth < 0:
                add(-0.15, f"營收衰退 {growth:.0%}")
        de = f.get("debtToEquity")
        if de is not None and de > 200:
            add(-0.2, f"負債權益比 {de:.0f}% 偏高")
        fcf = f.get("freeCashflow")
        if fcf is not None:
            add(0.1 if fcf > 0 else -0.2, "自由現金流為正" if fcf > 0 else "自由現金流為負")

        rationale = "、".join(notes) + "。" if notes else "基本面資料不足，暫持中立。"
        return View(snap.ticker, round(clamp(score), 4), rationale)
