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


@dataclass(frozen=True)
class Config:
    long_term: list[str] = field(default_factory=list)
    short_term: list[str] = field(default_factory=list)
    risk: RiskLimits = field(default_factory=RiskLimits)


def load_config(path: str | Path = "watchlist.toml") -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return Config(
        long_term=list(data.get("long_term", {}).get("tickers", [])),
        short_term=list(data.get("short_term", {}).get("tickers", [])),
        risk=RiskLimits(**data.get("risk", {})),
    )
