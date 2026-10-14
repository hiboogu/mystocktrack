import math
import random

import pytest

from mystocktrack.config import Config, RiskLimits
from mystocktrack.data import Snapshot, StaticDataProvider


def series(start: float, daily_drift: float, daily_vol: float, days: int = 280, seed: int = 1):
    rng = random.Random(seed)
    price, out = start, []
    for _ in range(days):
        price *= math.exp(daily_drift + rng.gauss(0, daily_vol))
        out.append(round(price, 4))
    return out


GOOD = {
    "quoteType": "EQUITY",
    "forwardPE": 18.0,
    "pegRatio": 1.2,
    "returnOnEquity": 0.30,
    "profitMargins": 0.25,
    "revenueGrowth": 0.12,
    "debtToEquity": 60.0,
    "freeCashflow": 1e10,
}
BAD = {
    "quoteType": "EQUITY",
    "forwardPE": 55.0,
    "pegRatio": 4.0,
    "returnOnEquity": 0.02,
    "profitMargins": 0.01,
    "revenueGrowth": -0.08,
    "debtToEquity": 320.0,
    "freeCashflow": -5e8,
}


@pytest.fixture
def snapshots():
    return {
        "QUAL": Snapshot("QUAL", series(100, 0.0008, 0.010, seed=1), GOOD),
        "JUNK": Snapshot("JUNK", series(100, -0.0015, 0.020, seed=2), BAD),
        "VOO": Snapshot("VOO", series(400, 0.0005, 0.008, seed=3), {"quoteType": "ETF"}),
        "BTC-USD": Snapshot("BTC-USD", series(60000, 0.0020, 0.040, seed=4), {}),
        "MSTR": Snapshot("MSTR", series(300, -0.0030, 0.050, seed=5), {}),
        "^GSPC": Snapshot("^GSPC", series(5000, 0.0005, 0.008, seed=6), {}),
        "^VIX": Snapshot("^VIX", [15.0] * 280, {}),
        "^TNX": Snapshot("^TNX", [4.0] * 280, {}),
    }


@pytest.fixture
def config():
    return Config(
        long_term=["QUAL", "JUNK", "VOO"],
        short_term=["BTC-USD", "MSTR"],
        risk=RiskLimits(),
    )


@pytest.fixture
def provider(snapshots):
    return StaticDataProvider(snapshots)


class FakeLLM:
    """Stands in for Claude: records prompts, bumps every draft score by a fixed amount."""

    def __init__(self, bump: float = 0.1, narrative: str = "經理摘要：測試用。"):
        self.bump = bump
        self.narrative = narrative
        self.calls: list[tuple[str, str]] = []

    def json(self, system, prompt, schema):
        import json

        self.calls.append((system, prompt))
        data = json.loads(prompt)
        if "draft" in data:
            return {
                "views": [
                    {
                        "ticker": d["ticker"],
                        "score": d["score"] + self.bump,
                        "rationale": "LLM 修正",
                    }
                    for d in data["draft"]
                ]
            }
        return {"score": 0.5, "rationale": "LLM 維持看多，但同意縮小部位"}

    def text(self, system, prompt):
        self.calls.append((system, prompt))
        return self.narrative
