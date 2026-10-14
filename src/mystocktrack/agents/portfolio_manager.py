"""Portfolio manager, the lead agent: assigns work, runs the debate round and decides."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date

from .. import DISCLAIMER
from .. import indicators as ind
from ..bus import BROADCAST, Message, MessageBus
from ..config import Config
from ..data import MACRO_TICKERS, DataProvider, Snapshot
from ..llm import LLM
from .base import AnalystAgent
from .crypto_trader import CryptoTrader
from .fundamentals import FundamentalsAnalyst
from .macro_sentiment import MacroSentimentAnalyst, market_regime
from .risk_manager import RiskManager

log = logging.getLogger(__name__)

LONG_TERM_WEIGHTS = {"fundamentals": 0.6, "macro_sentiment": 0.4}
SHORT_TERM_WEIGHTS = {"crypto_trader": 0.7, "macro_sentiment": 0.3}
MIN_SCORE_TO_HOLD = 0.1


@dataclass
class Position:
    ticker: str
    score: float
    weight: float
    action: str
    reasons: dict[str, str]
    extras: dict = field(default_factory=dict)


@dataclass
class HoldingReview:
    ticker: str
    shares: float
    cost: float
    price: float
    value: float
    pnl: float
    pnl_pct: float
    score: float
    action: str
    stop_price: float | None


@dataclass
class Recommendation:
    as_of: str
    long_term: list[Position]
    short_term: list[Position]
    cash: float
    regime_notes: list[str]
    narrative: str | None
    transcript: list[Message]
    skipped: list[str] = field(default_factory=list)
    holdings: list[HoldingReview] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


class PortfolioManager:
    name = "portfolio_manager"
    title = "投資組合經理（主導）"
    persona = (
        "你是投資組合經理，帶領基本面分析師、總經情緒分析師、比特幣短線交易員與風控經理。"
        "使用者偏好：美股長期配置，比特幣相關資產短線進出。請用繁體中文寫給一般投資人看的"
        "投資建議摘要，先講結論，再逐一說明使用者目前持股（holdings）該續抱、加碼、減碼或停損"
        "及理由，接著點評沒有持股的觀察名單，最後講風險並提醒這不是投資建議。"
    )

    def __init__(self, data: DataProvider, config: Config, llm: LLM | None = None):
        self.data = data
        self.config = config
        self.llm = llm

    def _fetch(self, tickers: list[str], skipped: list[str]) -> dict[str, Snapshot]:
        out = {}
        for t in tickers:
            try:
                out[t] = self.data.snapshot(t)
            except Exception as exc:  # one bad ticker should not sink the whole run
                log.warning("skipping %s: %s", t, exc)
                skipped.append(t)
        return out

    def run(self) -> Recommendation:
        bus = MessageBus()
        skipped: list[str] = []
        long_snaps = self._fetch(self.config.long_term, skipped)
        short_snaps = self._fetch(self.config.short_term, skipped)
        if not long_snaps and not short_snaps:
            raise RuntimeError(f"no market data for any ticker: {', '.join(skipped)}")
        macro = self._fetch(list(MACRO_TICKERS.values()), [])
        macro = {k: macro[v] for k, v in MACRO_TICKERS.items() if v in macro}
        regime_score, regime_notes = market_regime(macro)
        context = {
            "regime_score": regime_score,
            "regime_notes": regime_notes,
            "summary": {"market_regime_score": regime_score, "market_notes": regime_notes},
        }

        fundamentals = FundamentalsAnalyst(bus, self.llm)
        macro_agent = MacroSentimentAnalyst(bus, self.llm)
        trader = CryptoTrader(bus, self.llm)
        risk = RiskManager(bus, self.config.risk)
        all_snaps = {**long_snaps, **short_snaps}

        # 1. Assign work.
        bus.send(self.name, fundamentals.name, "task", f"評估長期持有價值：{', '.join(long_snaps)}")
        bus.send(self.name, macro_agent.name, "task", f"評估總經與情緒環境：{', '.join(all_snaps)}")
        bus.send(self.name, trader.name, "task", f"給出短線進出場判斷：{', '.join(short_snaps)}")
        bus.send(
            self.name,
            risk.name,
            "task",
            "審查所有分析師報告，對過度樂觀的看法提出質疑並設定部位上限。",
        )

        # 2. Analysts report.
        fundamentals.analyze(long_snaps, context, self.name)
        macro_agent.analyze(all_snaps, context, self.name)
        trader.analyze(short_snaps, context, self.name)

        # 3. Debate round: risk challenges, analysts answer.
        for snap in all_snaps.values():
            risk.profile(snap)
        analysts: list[AnalystAgent] = [fundamentals, macro_agent, trader]
        for agent, ticker, text in risk.review(analysts, all_snaps):
            agent.respond_to_challenge(ticker, text, all_snaps[ticker], self.name)

        # 4. Risk sign-off, then the lead decides.
        profiles = risk.assess(self.name)
        views = {a.name: a.views for a in analysts}
        short_term = self._short_term(short_snaps, views)
        crypto_total = sum(p.weight for p in short_term)
        long_term = self._long_term(long_snaps, views, profiles, budget=1 - crypto_total)
        holdings = self._review_holdings(all_snaps, long_term + short_term, set(short_snaps))
        # Rounded weights can overshoot by a hair; never report negative cash.
        cash = max(0.0, round(1 - crypto_total - sum(p.weight for p in long_term), 4))

        rec = Recommendation(
            as_of=date.today().isoformat(),
            long_term=long_term,
            short_term=short_term,
            cash=cash,
            regime_notes=regime_notes,
            narrative=None,
            transcript=bus.transcript,
            skipped=skipped,
            holdings=holdings,
        )
        rec.narrative = self._narrative(rec)
        bus.send(self.name, BROADCAST, "decision", self._decision_line(rec))
        return rec

    @staticmethod
    def _blend(ticker: str, views: dict, weights: dict[str, float]) -> tuple[float, dict]:
        total, used, reasons = 0.0, 0.0, {}
        for agent, w in weights.items():
            v = views.get(agent, {}).get(ticker)
            if v:
                total += w * v.score
                used += w
                reasons[agent] = v.rationale
        return (round(total / used, 4) if used else 0.0), reasons

    def _long_term(self, snaps, views, profiles, budget: float) -> list[Position]:
        scored = []
        for t in snaps:
            score, reasons = self._blend(t, views, LONG_TERM_WEIGHTS)
            scored.append((t, score, reasons))
        caps = {t: profiles[t].cap for t in snaps}
        weights = allocate({t: s for t, s, _ in scored if s >= MIN_SCORE_TO_HOLD}, caps, budget)
        positions = []
        for t, score, reasons in sorted(scored, key=lambda x: -x[1]):
            w = weights.get(t, 0.0)
            if t in self.config.holdings:
                action = "已持有（見持股檢視）"
            else:
                action = "可考慮建倉" if w > 0 else ("避開" if score < 0 else "觀察")
            positions.append(Position(t, score, w, action, reasons))
        return positions

    def _short_term(self, snaps, views) -> list[Position]:
        blended = {t: self._blend(t, views, SHORT_TERM_WEIGHTS) for t in snaps}
        buys = [t for t, (s, _) in blended.items() if s >= 0.3]
        each = round(self.config.risk.max_crypto_sleeve / len(snaps), 4) if snaps else 0.0
        positions = []
        for t, (score, reasons) in sorted(blended.items(), key=lambda x: -x[1][0]):
            extras = views["crypto_trader"][t].extras if t in views["crypto_trader"] else {}
            positions.append(
                Position(
                    t,
                    score,
                    each if t in buys else 0.0,
                    CryptoTrader.signal(score),
                    reasons,
                    extras,
                )
            )
        return positions

    def _review_holdings(
        self, snaps: dict[str, Snapshot], positions: list[Position], short_term: set[str]
    ) -> list[HoldingReview]:
        scores = {p.ticker: p for p in positions}
        reviews = []
        for t, h in self.config.holdings.items():
            if t not in snaps or t not in scores:
                continue  # no price today; the ticker already shows under skipped
            snap, pos = snaps[t], scores[t]
            price = snap.price
            pnl_pct = price / h.cost - 1 if h.cost else 0.0
            if t in short_term:
                stop = pos.extras.get("stop_loss")
            else:
                atr = ind.avg_true_range_pct(snap.closes, 14)
                stop = round(price * (1 - 3 * atr), 2) if atr else None
            reviews.append(
                HoldingReview(
                    ticker=t,
                    shares=h.shares,
                    cost=h.cost,
                    price=round(price, 2),
                    value=round(price * h.shares, 2),
                    pnl=round((price - h.cost) * h.shares, 2),
                    pnl_pct=round(pnl_pct, 4),
                    score=pos.score,
                    action=holding_action(pos.score, pnl_pct, self.config.risk.max_loss_from_cost),
                    stop_price=stop,
                )
            )
        return sorted(reviews, key=lambda r: r.pnl_pct)

    def _narrative(self, rec: Recommendation) -> str | None:
        if not self.llm:
            return None
        payload = {
            "as_of": rec.as_of,
            "market": rec.regime_notes,
            "long_term": [_pos_dict(p) for p in rec.long_term],
            "short_term": [_pos_dict(p) for p in rec.short_term],
            "cash": rec.cash,
            "holdings": [asdict(h) for h in rec.holdings],
            "watch_only": [p.ticker for p in rec.long_term if p.ticker not in self.config.holdings],
            "debate": [
                f"{m.sender} → {m.recipient}：{m.content}"
                for m in rec.transcript
                if m.kind in ("challenge", "rebuttal")
            ],
        }
        return self.llm.text(self.persona, json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _decision_line(rec: Recommendation) -> str:
        held = [f"{p.ticker} {p.weight:.0%}" for p in rec.long_term if p.weight > 0]
        trades = [f"{p.ticker} {p.action}" for p in rec.short_term]
        return (
            f"長期配置：{', '.join(held) or '無'}；短線：{', '.join(trades) or '無'}；"
            f"現金 {rec.cash:.0%}。"
        )


def holding_action(score: float, pnl_pct: float, max_loss: float) -> str:
    """What to do with a stock the user already owns, from the team's score and the P&L."""
    if score <= -0.3:
        return "獲利了結" if pnl_pct > 0 else "停損出場"
    if pnl_pct <= -max_loss and score < 0.3:
        return "停損出場"
    if score < MIN_SCORE_TO_HOLD:
        return "減碼"
    if score >= 0.3:
        return "可加碼"
    return "續抱"


def allocate(scores: dict[str, float], caps: dict[str, float], budget: float) -> dict[str, float]:
    """Split budget in proportion to score, respecting per-ticker caps; the remainder stays cash."""
    weights: dict[str, float] = {}
    remaining = dict(scores)
    left = budget
    while remaining and left > 1e-9:
        total = sum(remaining.values())
        capped = {t: caps[t] - weights.get(t, 0) for t in remaining}
        share = {t: left * s / total for t, s in remaining.items()}
        over = [t for t in remaining if share[t] >= capped[t]]
        if not over:
            for t, w in share.items():
                weights[t] = weights.get(t, 0) + w
            break
        for t in over:
            weights[t] = caps[t]
            left -= capped[t]
            del remaining[t]
    return {t: round(w, 4) for t, w in weights.items()}


def _pos_dict(p: Position) -> dict:
    return {
        "ticker": p.ticker,
        "score": p.score,
        "weight": p.weight,
        "action": p.action,
        "reasons": p.reasons,
        **({"levels": p.extras} if p.extras else {}),
    }
