"""Shared analyst behaviour: rule-based draft, optional Claude refinement, and answering challenges."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..bus import MessageBus
from ..data import Snapshot
from ..llm import LLM

VIEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "views": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "score": {"type": "number"},
                    "rationale": {"type": "string"},
                },
                "required": ["ticker", "score", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["views"],
    "additionalProperties": False,
}

REBUTTAL_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "number"}, "rationale": {"type": "string"}},
    "required": ["score", "rationale"],
    "additionalProperties": False,
}

LANGUAGE_RULE = "所有 rationale 請用繁體中文，一到兩句，引用給你的數據。"


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class View:
    """One agent's view on one ticker. score runs from -1 (bearish) to +1 (bullish)."""

    ticker: str
    score: float
    rationale: str
    extras: dict = field(default_factory=dict)
    revised: bool = False

    @property
    def stance(self) -> str:
        if self.score >= 0.3:
            return "看多"
        if self.score <= -0.3:
            return "看空"
        return "中立"


class AnalystAgent:
    name = "analyst"
    title = "分析師"
    persona = ""

    def __init__(self, bus: MessageBus, llm: LLM | None = None):
        self.bus = bus
        self.llm = llm
        self.views: dict[str, View] = {}

    # Subclasses implement the deterministic analysis.
    def rule_view(self, snap: Snapshot, context: dict) -> View:
        raise NotImplementedError

    def evidence(self, snap: Snapshot) -> dict:
        return {"ticker": snap.ticker, "metrics": snap.metrics()}

    def analyze(self, snapshots: dict[str, Snapshot], context: dict, lead: str) -> dict[str, View]:
        drafts = {t: self.rule_view(s, context) for t, s in snapshots.items()}
        self.views = self._refine(drafts, snapshots, context)
        for v in self.views.values():
            self.bus.send(
                self.name,
                lead,
                "report",
                f"{v.ticker}：{v.stance}（{v.score:+.2f}）。{v.rationale}",
                ticker=v.ticker,
                score=v.score,
            )
        return self.views

    def _refine(self, drafts, snapshots, context) -> dict[str, View]:
        if not self.llm:
            return drafts
        prompt = json.dumps(
            {
                "task": "根據證據檢查並修正規則引擎的初稿分數（-1 看空到 +1 看多）。",
                "context": context.get("summary", {}),
                "evidence": [self.evidence(s) for s in snapshots.values()],
                "draft": [
                    {"ticker": v.ticker, "score": v.score, "rationale": v.rationale}
                    for v in drafts.values()
                ],
            },
            ensure_ascii=False,
        )
        out = self.llm.json(f"{self.persona}\n{LANGUAGE_RULE}", prompt, VIEWS_SCHEMA)
        if not out:
            return drafts
        for item in out.get("views", []):
            v = drafts.get(item.get("ticker"))
            if v:
                v.score = clamp(float(item["score"]))
                v.rationale = item["rationale"]
        return drafts

    def respond_to_challenge(self, ticker: str, challenge: str, snap: Snapshot, lead: str) -> View:
        """Answer the risk manager. Without Claude, conviction is cut by 40% to respect the risk."""
        view = self.views[ticker]
        answer = None
        if self.llm:
            prompt = json.dumps(
                {
                    "task": "風控經理質疑你的看法。請決定維持或下修分數，並說明理由。",
                    "your_view": {"score": view.score, "rationale": view.rationale},
                    "challenge": challenge,
                    "evidence": self.evidence(snap),
                },
                ensure_ascii=False,
            )
            answer = self.llm.json(f"{self.persona}\n{LANGUAGE_RULE}", prompt, REBUTTAL_SCHEMA)
        if answer:
            view.score = clamp(float(answer["score"]))
            view.rationale = answer["rationale"]
        else:
            view.score = round(view.score * 0.6, 4)
            view.rationale += "（回應風控：考量波動與回撤，下修信心。）"
        view.revised = True
        self.bus.send(
            self.name,
            "risk_manager",
            "rebuttal",
            f"{ticker}：調整後 {view.stance}（{view.score:+.2f}）。{view.rationale}",
            ticker=ticker,
            score=view.score,
        )
        return view
