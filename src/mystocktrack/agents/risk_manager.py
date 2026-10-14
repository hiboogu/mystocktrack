"""Risk manager: challenges bullish views on risky assets and sets position caps."""

from __future__ import annotations

from dataclasses import dataclass

from .. import indicators as ind
from ..bus import MessageBus
from ..config import RiskLimits
from ..data import Snapshot
from .base import AnalystAgent


@dataclass
class RiskProfile:
    ticker: str
    volatility: float | None
    drawdown: float | None
    high_risk: bool
    cap: float


class RiskManager:
    name = "risk_manager"
    title = "風控經理"

    def __init__(self, bus: MessageBus, limits: RiskLimits):
        self.bus = bus
        self.limits = limits
        self.profiles: dict[str, RiskProfile] = {}

    def profile(self, snap: Snapshot) -> RiskProfile:
        vol = ind.annualized_volatility(snap.closes)
        dd = ind.max_drawdown(snap.closes)
        high = (vol or 0) > self.limits.high_volatility or (dd or 0) > self.limits.deep_drawdown
        cap = self.limits.max_single_weight * (0.5 if high else 1.0)
        p = RiskProfile(snap.ticker, vol, dd, high, round(cap, 4))
        self.profiles[snap.ticker] = p
        return p

    def review(
        self, analysts: list[AnalystAgent], snapshots: dict[str, Snapshot]
    ) -> list[tuple[AnalystAgent, str, str]]:
        """Send a challenge for each bullish view on a high-risk asset; return them to be answered."""
        challenges = []
        for agent in analysts:
            for ticker, view in agent.views.items():
                p = self.profiles.get(ticker) or self.profile(snapshots[ticker])
                if view.score >= 0.3 and p.high_risk:
                    text = (
                        f"{ticker} 年化波動 {_pct(p.volatility)}、一年最大回撤 {_pct(p.drawdown)}，"
                        f"超過風控門檻。你給 {view.score:+.2f} 看多，請說明理由或下修。"
                    )
                    self.bus.send(self.name, agent.name, "challenge", text, ticker=ticker)
                    challenges.append((agent, ticker, text))
        return challenges

    def assess(self, lead: str) -> dict[str, RiskProfile]:
        for p in self.profiles.values():
            flag = "高風險，部位上限減半" if p.high_risk else "風險在門檻內"
            self.bus.send(
                self.name,
                lead,
                "risk_assessment",
                f"{p.ticker}：波動 {_pct(p.volatility)}、回撤 {_pct(p.drawdown)}，{flag}，"
                f"單一部位上限 {p.cap:.0%}。",
                ticker=p.ticker,
                cap=p.cap,
                high_risk=p.high_risk,
            )
        self.bus.send(
            self.name,
            lead,
            "risk_assessment",
            f"比特幣相關短線部位合計上限 {self.limits.max_crypto_sleeve:.0%}。",
            crypto_sleeve=self.limits.max_crypto_sleeve,
        )
        return self.profiles


def _pct(x: float | None) -> str:
    return "N/A" if x is None else f"{x:.0%}"
