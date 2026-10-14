"""Command-line entry point: run Claude and GPT independently on one frozen dataset."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .agents import PortfolioManager
from .config import load_config
from .data import YahooDataProvider
from .llm import default_llm
from .openai_llm import default_openai_llm
from .holdings import holdings_markdown
from .report import to_html, to_json, to_markdown
from .shared_snapshot import capture, load_snapshot, save_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mystocktrack")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run independent research reports")
    run.add_argument("--config", default="watchlist.toml")
    run.add_argument("--out", default="reports")
    run.add_argument("--models", choices=["both", "claude", "gpt"], default="both")
    run.add_argument("--snapshot", help="reuse a previously saved market-data JSON snapshot")
    run.add_argument("--portfolio", default="portfolio.toml", help="portfolio holdings file")
    run.add_argument("--offline", action="store_true", help="use deterministic rule engines only")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config(args.config)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.snapshot:
        provider = load_snapshot(args.snapshot)
    else:
        provider, frozen = capture(config, YahooDataProvider())
        save_snapshot(frozen, out / "snapshot.json")

    models = ("claude", "gpt") if args.models == "both" else (args.models,)
    for model in models:
        llm = default_llm(args.offline) if model == "claude" else default_openai_llm(args.offline)
        if llm is None and not args.offline:
            raise RuntimeError(
                f"{model} API key missing. Set the provider key, or explicitly use --offline."
            )
        rec = PortfolioManager(provider, config, llm).run()
        directory = out / model
        directory.mkdir(parents=True, exist_ok=True)
        md = to_markdown(rec)
        if Path(args.portfolio).exists():
            md += "\n" + holdings_markdown(args.portfolio, provider)
        for name in (f"{rec.as_of}.md", "latest.md"):
            (directory / name).write_text(md, encoding="utf-8")
        (directory / f"{rec.as_of}.json").write_text(to_json(rec), encoding="utf-8")
        (directory / "index.html").write_text(
            to_html(md, f"{model.upper()} 投資研究報告 {rec.as_of}"), encoding="utf-8"
        )
        print(f"{model}: {directory / 'latest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
