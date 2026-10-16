"""Macro regime and market sentiment analyst: index trend, VIX, rates and price momentum."""

from __future__ import annotations

from .. import indicators as ind
from ..data import Snapshot
from .base import AnalystAgent, View, clamp


def market_regime(macro: dict[str, Snapshot]) -> tuple[float, list[str]]:
    """Score the overall market backdrop from S&P 500 trend, VIX and the 10-year yield."""
    score, notes = 0.0, []
    spx = macro.get("spx")
    if spx:
        sma200 = ind.sma(spx.closes, 200)
        if sma200:
            above = spx.price > sma200
            score += 0.2 if above else -0.3
            notes.append("S&P 500 在 200 日均線之上" if above else "S&P 500 跌破 200 日均線")
    vix = macro.get("vix")
    if vix:
        if vix.price < 18:
            score += 0.1
            notes.append(f"VIX {vix.price:.1f} 情緒平穩")
        elif vix.price > 28:
            score -= 0.3
            notes.append(f"VIX {vix.price:.1f} 市場恐慌")
    tnx = macro.get("tnx")
    if tnx:
        change = ind.pct_return(tnx.closes, 63)
        if change is not None and change > 0.10:
            score -= 0.15
            notes.append("十年期殖利率三個月內快速上升")
    return round(score, 4), notes


def japan_regime(macro: dict[str, Snapshot]) -> tuple[float, list[str]]:
    """Score the backdrop for Tokyo-listed stocks from the Nikkei 225 trend and the yen."""
    score, notes = 0.0, []
    nikkei = macro.get("nikkei")
    if nikkei:
        sma200 = ind.sma(nikkei.closes, 200)
        if sma200:
            above = nikkei.price > sma200
            score += 0.2 if above else -0.3
            notes.append("日經 225 在 200 日均線之上" if above else "日經 225 跌破 200 日均線")
    usdjpy = macro.get("usdjpy")
    if usdjpy:
        notes.append(f"美元兌日圓 {usdjpy.price:.1f}")
        change = ind.pct_return(usdjpy.closes, 63)
        if change is not None and change > 0.05:
            notes.append(
                f"日圓三個月內走弱 {change:.0%}：有利日本出口商獲利，但以美元計的報酬會被匯率吃掉"
            )
        elif change is not None and change < -0.05:
            score -= 0.1
            notes.append(
                f"日圓三個月內走強 {-change:.0%}：壓抑日本出口商獲利，以美元計則有匯兌收益"
            )
    return round(score, 4), notes


class MacroSentimentAnalyst(AnalystAgent):
    name = "macro_sentiment"
    title = "總經與市場情緒分析師"
    persona = (
        "你是總經與市場情緒分析師，從利率、波動率指數、大盤趨勢與個股動能判斷"
        "現在的環境對該資產是順風還是逆風。日股（代號 .T，以日圓計價）請改看日經指數與日圓匯率，"
        "並說明匯率對以美元計報酬的影響。"
    )

    def rule_view(self, snap: Snapshot, context: dict) -> View:
        if snap.market == "JP":
            score = context.get("japan_regime_score", 0.0)
            notes = list(context.get("japan_regime_notes", []))
        else:
            score = context.get("regime_score", 0.0)
            notes = list(context.get("regime_notes", []))
        c = snap.closes
        r12 = ind.pct_return(c, 252)
        if r12 is not None:
            score += 0.2 if r12 > 0 else -0.2
            notes.append(f"12 個月報酬 {r12:+.0%}")
        r6 = ind.pct_return(c, 126)
        if r6 is not None and r6 > 0:
            score += 0.1
        sma200 = ind.sma(c, 200)
        if sma200:
            above = snap.price > sma200
            score += 0.15 if above else -0.15
            notes.append("股價在 200 日均線之上" if above else "股價在 200 日均線之下")
        return View(snap.ticker, round(clamp(score), 4), "、".join(notes) + "。")
