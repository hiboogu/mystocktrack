"""Watchlist and risk limits, loaded from watchlist.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RiskLimits:
    max_single_weight: float = 0.20
    max_crypto_sleeve: float = 0.10
    high_volatility: float = 0.45
    deep_drawdown: float = 0.35
    max_loss_from_cost: float = 0.30


@dataclass(frozen=True)
class Holding:
    """A position the user already owns: average cost per share and share count."""

    cost: float
    shares: float


@dataclass(frozen=True)
class Config:
    long_term: list[str] = field(default_factory=list)
    short_term: list[str] = field(default_factory=list)
    risk: RiskLimits = field(default_factory=RiskLimits)
    holdings: dict[str, Holding] = field(default_factory=dict)


def load_config(path: str | Path = "watchlist.toml") -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    long_term = list(data.get("long_term", {}).get("tickers", []))
    short_term = list(data.get("short_term", {}).get("tickers", []))
    holdings = {t: Holding(**h) for t, h in data.get("holdings", {}).items()}
    # Anything held is always analyzed; unlisted holdings default to the long-term group.
    long_term += [t for t in holdings if t not in long_term and t not in short_term]
    return Config(long_term, short_term, RiskLimits(**data.get("risk", {})), holdings)
