"""Command line entry point: `mystocktrack run`."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .agents import PortfolioManager
from .config import load_config
from .data import YahooDataProvider
from .llm import default_llm
from .report import to_html, to_json, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mystocktrack")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the agent team and write a report")
    run.add_argument("--config", default="watchlist.toml")
    run.add_argument("--out", default="reports")
    run.add_argument(
        "--offline", action="store_true", help="rule-based agents only, no Claude calls"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config = load_config(args.config)
    pm = PortfolioManager(YahooDataProvider(), config, default_llm(args.offline))
    rec = pm.run()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md = to_markdown(rec)
    for name in (f"{rec.as_of}.md", "latest.md"):
        (out / name).write_text(md, encoding="utf-8")
    (out / f"{rec.as_of}.json").write_text(to_json(rec), encoding="utf-8")
    (out / "index.html").write_text(to_html(md, f"投資建議報告 {rec.as_of}"), encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
