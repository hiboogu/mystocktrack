"""Fetch all input data once and reuse an immutable-in-practice snapshot."""
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .data import MACRO_TICKERS, Snapshot, StaticDataProvider


def capture(config, provider):
    tickers = list(dict.fromkeys(
        [*config.long_term, *config.short_term, *MACRO_TICKERS.values()]
    ))
    snapshots, failures = {}, {}
    for ticker in tickers:
        try:
            snapshots[ticker] = provider.snapshot(ticker)
        except Exception as exc:
            failures[ticker] = str(exc)
    frozen = {
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "requested_tickers": tickers,
        "snapshots": {t: asdict(s) for t, s in snapshots.items()},
        "failures": failures,
    }
    return StaticDataProvider(snapshots), frozen


def save_snapshot(frozen, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshot(path):
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    return StaticDataProvider({
        ticker: Snapshot(**value)
        for ticker, value in frozen["snapshots"].items()
    })
