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
from .valuation import load_state, save_state, update_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mystocktrack")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the agent team and write a report")
    run.add_argument("--config", default="watchlist.toml")
    run.add_argument("--out", default="reports")
    run.add_argument(
        "--state",
        default="state/ratings.json",
        help="prior ratings and target prices; read for 「前次」 and rewritten after the run",
    )
    run.add_argument(
        "--offline", action="store_true", help="rule-based agents only, no Claude calls"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config = load_config(args.config)
    llm = default_llm(args.offline)
    logging.info("Claude analysis: %s", "on" if llm else "off (rule-based only)")
    pm = PortfolioManager(YahooDataProvider(), config, llm)
    rec = pm.run()
    state = update_state(load_state(args.state), rec.valuations, rec.as_of)
    save_state(args.state, state)

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
