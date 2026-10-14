"""Render a Recommendation as Markdown and JSON."""

from __future__ import annotations

import html
import json
from dataclasses import asdict

from .agents import Recommendation

AGENT_TITLES = {
    "portfolio_manager": "投資組合經理",
    "fundamentals": "基本面分析師",
    "macro_sentiment": "總經情緒分析師",
    "crypto_trader": "BTC 短線交易員",
    "risk_manager": "風控經理",
    "*": "全體",
}

KIND_TITLES = {
    "task": "指派",
    "report": "報告",
    "challenge": "質疑",
    "rebuttal": "回應",
    "risk_assessment": "風控",
    "decision": "裁決",
}


HTML_PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: system-ui, "Noto Sans TC", sans-serif; max-width: 1100px; margin: 0 auto;
        padding: 16px; line-height: 1.6; color: #1f2328; background: #fff; }}
table {{ border-collapse: collapse; width: 100%; display: block; overflow-x: auto; }}
th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; vertical-align: top; }}
th {{ background: #f6f8fa; }}
blockquote {{ color: #9a6700; border-left: 4px solid #d4a72c; margin: 0; padding-left: 12px; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #e6edf3; background: #0d1117; }}
  th {{ background: #161b22; }}
  th, td {{ border-color: #30363d; }}
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _t(name: str) -> str:
    return AGENT_TITLES.get(name, name)


def to_markdown(rec: Recommendation) -> str:
    lines = [f"# 投資建議報告 {rec.as_of}", "", f"> {rec.disclaimer}", ""]
    if rec.narrative:
        lines += ["## 經理摘要", "", rec.narrative.strip(), ""]
    if rec.regime_notes:
        lines += ["## 市場環境", "", *[f"- {n}" for n in rec.regime_notes], ""]

    lines += [
        "## 美股長期配置",
        "",
        "| 標的 | 綜合分數 | 建議權重 | 動作 | 基本面 | 總經情緒 |",
        "|---|---|---|---|---|---|",
    ]
    for p in rec.long_term:
        lines.append(
            f"| {p.ticker} | {p.score:+.2f} | {p.weight:.1%} | {p.action} | "
            f"{p.reasons.get('fundamentals', '')} | {p.reasons.get('macro_sentiment', '')} |"
        )
    lines += [
        "",
        "## 比特幣相關短線",
        "",
        "| 標的 | 綜合分數 | 訊號 | 建議權重 | 進場 | 停損 | 停利 | 理由 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in rec.short_term:
        e = p.extras
        lines.append(
            f"| {p.ticker} | {p.score:+.2f} | {p.action} | {p.weight:.1%} | "
            f"{e.get('entry', '')} | {e.get('stop_loss', '')} | {e.get('take_profit', '')} | "
            f"{p.reasons.get('crypto_trader', '')} |"
        )
    lines += ["", f"**現金：{rec.cash:.1%}**", ""]
    if rec.skipped:
        lines += [f"資料抓取失敗、本次略過：{', '.join(rec.skipped)}", ""]

    lines += ["## 角色對話紀錄", ""]
    for m in rec.transcript:
        lines.append(
            f"- **{_t(m.sender)} → {_t(m.recipient)}**（{KIND_TITLES.get(m.kind, m.kind)}）："
            f"{m.content}"
        )
    return "\n".join(lines) + "\n"


def to_html(markdown_text: str, title: str) -> str:
    """Wrap the Markdown report in a standalone page (needs the optional `markdown` package)."""
    try:
        import markdown

        body = markdown.markdown(markdown_text, extensions=["tables"])
    except ImportError:
        body = f"<pre>{html.escape(markdown_text)}</pre>"
    return HTML_PAGE.format(title=html.escape(title), body=body)


def to_json(rec: Recommendation) -> str:
    return json.dumps(asdict(rec), ensure_ascii=False, indent=2)
