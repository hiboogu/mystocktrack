"""Render a Recommendation as Markdown and JSON."""

from __future__ import annotations

import html
import json
from dataclasses import asdict

from .agents import Recommendation
from .data import market_of
from .financials import ANNUAL_YEARS, ESTIMATE_PERIODS
from .valuation import METHOD_NAMES, RATING_TABLE

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


def label(ticker: str, names: dict[str, str]) -> str:
    """Ticker plus display name; Tokyo stocks are marked as priced in yen."""
    extra = [names[ticker]] if ticker in names else []
    if market_of(ticker) == "JP":
        extra.append("日股，日圓計價")
    return f"{ticker}（{'，'.join(extra)}）" if extra else ticker


def to_markdown(rec: Recommendation) -> str:
    lines = [f"# 投資建議報告 {rec.as_of}", "", f"> {rec.disclaimer}", ""]
    if rec.narrative:
        lines += ["## 經理摘要", "", rec.narrative.strip(), ""]
    if rec.regime_notes:
        lines += ["## 市場環境", "", *[f"- {n}" for n in rec.regime_notes], ""]
    if rec.holdings:
        cost = sum(h.cost * h.shares for h in rec.holdings)
        value = sum(h.value for h in rec.holdings)
        pnl = value - cost
        lines += [
            "## 我的持股檢視",
            "",
            f"市值 ${value:,.2f}，成本 ${cost:,.2f}，未實現損益 ${pnl:+,.2f}"
            f"（{pnl / cost if cost else 0:+.1%}）",
            "",
            "| 標的 | 股數 | 成本 | 現價 | 市值 | 未實現損益 | 報酬率 | 綜合分數 | 建議 | 停損參考 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for h in rec.holdings:
            stop = f"{h.stop_price:,.2f}" if h.stop_price else ""
            name = f"{h.ticker}（投機）" if h.speculative else h.ticker
            lines.append(
                f"| {name} | {h.shares:g} | {h.cost:,.2f} | {h.price:,.2f} | {h.value:,.2f} | "
                f"{h.pnl:+,.2f} | {h.pnl_pct:+.1%} | {h.score:+.2f} | **{h.action}** | {stop} |"
            )
        lines.append("")
        for h in (h for h in rec.holdings if h.speculative):
            lines.append(
                f"- **{h.ticker}** 為投機部位：占持股 {h.weight:.1%}，硬停損 {h.stop_price:,.2f}"
                f"；催化劑：{h.catalyst or '未填'}；檢討日：{h.review_by or '未填'}。"
                "分數僅供參考，不依長期規則出場。"
            )
        if any(h.speculative for h in rec.holdings):
            lines.append("")

    if rec.valuations:
        lines += ratings_section(rec)

    lines += [
        "## 美股長期配置（含觀察名單）",
        "",
        "| 標的 | 綜合分數 | 建議權重 | 動作 | 基本面 | 總經情緒 |",
        "|---|---|---|---|---|---|",
    ]
    for p in rec.long_term:
        lines.append(
            f"| {label(p.ticker, rec.names)} | {p.score:+.2f} | {p.weight:.1%} | {p.action} | "
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

    if rec.financials or rec.holdings or rec.long_term:
        lines += earnings_section(rec)

    lines += ["## 角色對話紀錄", ""]
    for m in rec.transcript:
        lines.append(
            f"- **{_t(m.sender)} → {_t(m.recipient)}**（{KIND_TITLES.get(m.kind, m.kind)}）："
            f"{m.content}"
        )
    return "\n".join(lines) + "\n"


NO_DATA = "資料不足"


def _money(x: float | None, currency: str) -> str:
    """Large amounts in millions (USD) or 億 (JPY), per the report standard's unit rule."""
    if x is None:
        return NO_DATA
    if currency == "JPY":
        return f"{x / 1e8:,.0f}"
    return f"{x / 1e6:,.0f}"


def _unit(currency: str) -> str:
    return "億日圓" if currency == "JPY" else f"百萬{'美元' if currency == 'USD' else currency}"


def _f(x: float | None, fmt: str = "{:,.2f}") -> str:
    return NO_DATA if x is None else fmt.format(x)


def _pct(x: float | None) -> str:
    return NO_DATA if x is None else f"{x:+.1%}"


def _x(m: float | None) -> str:
    return NO_DATA if m is None else f"{m:.1f} 倍"


def _prior(v: dict, key: str, fmt: str = "{}") -> str:
    p = v.get("prior") or {}
    if p.get(key) is None:
        return "—"
    return fmt.format(p[key]) + (f"（{p['date']}）" if key == "rating" and p.get("date") else "")


def ratings_section(rec: Recommendation) -> list[str]:
    """Summary table of ratings and 6-month targets, plus the rating definitions."""
    held = [h.ticker for h in rec.holdings]
    order = [*(t for t in held if t in rec.valuations)]
    order += [t for t in rec.valuations if t not in order]
    lines = [
        "## 評等與目標價（6 個月）",
        "",
        "| 標的 | 評等 | 前次評等 | 現價 | 目標價 | 前次目標價 | 潛在漲跌 | 方法 | 目前倍數 | 歷史區間（20／50／80 百分位） | 悲觀／基本／樂觀 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in order:
        v = rec.valuations[t]
        band = v.get("band")
        band_txt = "／".join(f"{b:.1f}" for b in band) + " 倍" if band else NO_DATA
        scen = v.get("scenarios") or []
        scen_txt = "／".join(f"{s['price']:,.2f}" for s in scen) if scen else NO_DATA
        lines.append(
            f"| {label(t, rec.names)} | **{v['rating']}** | {_prior(v, 'rating')} | "
            f"{_f(v.get('price'))} | {_f(v.get('target'))} | {_prior(v, 'target', '{:,.2f}')} | "
            f"{_pct(v.get('upside'))} | {METHOD_NAMES.get(v.get('method'), '—')} | "
            f"{_x(v.get('current_multiple'))} | "
            f"{band_txt} | {scen_txt} |"
        )
    lines += [
        "",
        "評等以基本情境目標價的 6 個月預估報酬（目標價 ÷ 現價 − 1）決定："
        + "、".join(f"{name} {rule}" for name, rule in RATING_TABLE)
        + "。目標價由程式依各股自己的歷史倍數區間推算，不是分析師共識，各股推導見「財報與預期」。",
        "",
    ]
    return lines


def valuation_lines(v: dict, cur: str) -> list[str]:
    if not v.get("method"):
        return [f"- 估值：{v['rating']}，{v.get('note') or NO_DATA}"]
    name = METHOD_NAMES[v["method"]]
    unit = "EPS" if v["method"] == "PE" else "每股營收"
    p20, p50, p80 = v["band"]
    out = [
        f"- 估值方法：{name}。{v['method_reason']}。",
        f"- 歷史區間：{v['band_period']} 共 {v['band_months']} 個月，以{v['band_basis']}計算，"
        f"20／50／80 百分位為 {p20:.1f}／{p50:.1f}／{p80:.1f} 倍；{v['multiple_reason']}。",
        f"- 目標價 ＝ {v['multiple']:.1f} 倍 × 6 個月後的近四季{unit} {v['metric_6m']:,.2f} {cur}"
        f"（現在 {v['metric_now']:,.2f}，取現在與未來 12 個月共識的中間）＝ {v['target']:,.2f}，"
        f"潛在漲跌 {_pct(v['upside'])}，評等 **{v['rating']}**。",
    ]
    for s in v.get("scenarios") or []:
        out.append(
            f"  - {s['name']}：{s['multiple']:.1f} 倍 × {s['metric']:,.2f} ＝ {s['price']:,.2f}"
            f"（{_pct(s['upside'])}），{s['trigger']}"
        )
    c = v.get("cross_check")
    if c:
        out.append(
            f"- 交叉驗證（{METHOD_NAMES[c['method']]}，{c['multiple']:.1f} 倍）：目標 "
            f"{c['target']:,.2f}，潛在漲跌 {_pct(c['upside'])}"
        )
    return out


def earnings_section(rec: Recommendation) -> list[str]:
    """Per stock: 3 fiscal years of key figures, last quarter vs consensus, estimates, next date."""
    held = [h.ticker for h in rec.holdings]
    order = [*held, *(p.ticker for p in rec.long_term if p.ticker not in held)]
    order += [
        p.ticker for p in rec.short_term if p.ticker in rec.financials and p.ticker not in order
    ]
    lines = [
        "## 財報與預期",
        "",
        "資料來源：Yahoo Finance（yfinance）。財報日以公司官方公告為準；"
        "「資料不足」表示 Yahoo 沒有提供該項（ETF、虧損公司或日股常見）。",
        "",
    ]
    for t in order:
        fin = rec.financials.get(t)
        lines.append(f"### {label(t, rec.names)}")
        lines.append("")
        if not fin:
            lines += [f"{NO_DATA}：Yahoo 沒有這檔的財報與預估資料。", ""]
            continue
        cur = fin.get("currency") or "USD"
        annual = list(reversed((fin.get("annual") or [])[:ANNUAL_YEARS]))
        if annual:
            lines += [
                f"重要營運數據（金額單位：{_unit(cur)}；每股數字單位：{cur}）",
                "",
                "| 會計年度 | 營收 | 營收 YoY | 每股營收 | EPS | 自由現金流 | 資本支出 |",
                "|---|---|---|---|---|---|---|",
            ]
            for r in annual:
                lines.append(
                    f"| {r['period']} | {_money(r.get('revenue'), cur)} | {_pct(r.get('revenue_yoy'))} | "
                    f"{_f(r.get('revenue_per_share'))} | {_f(r.get('eps'))} | {_money(r.get('fcf'), cur)} | "
                    f"{_money(r.get('capex'), cur)} |"
                )
            lines.append("")
        else:
            lines += [f"- 年度財報：{NO_DATA}", ""]

        s = (fin.get("eps_surprises") or [None])[0]
        if s:
            streak = fin.get("beat_streak", 0)
            tail = (
                f"；連續 {streak} 季優於共識"
                if streak > 1
                else f"；連續 {-streak} 季低於共識"
                if streak < -1
                else ""
            )
            lines.append(
                f"- 最近一季（{s['period']}）EPS 實際 {_f(s['actual'])}，共識 {_f(s['estimate'])}，"
                f"差異 {_pct(s['surprise'])}{tail}"
            )
        else:
            lines.append(f"- 最近一季 EPS vs 共識：{NO_DATA}")
        # Tokyo stocks often have a newest quarter with only EPS filled in; skip to one with revenue.
        q = next((r for r in fin.get("quarters") or [] if r.get("revenue") is not None), None)
        if q:
            lines.append(
                f"- 最近一季（{q['period']}）營收 {_money(q['revenue'], cur)}（{_unit(cur)}，"
                f"YoY {_pct(q.get('revenue_yoy'))}），毛利率 {_f(q['gross_margin'], '{:.1%}')}，"
                f"營益率 {_f(q['operating_margin'], '{:.1%}')}"
            )
        est = fin.get("estimates") or {}
        for code in ("0q", "0y", "+1y"):
            e = est.get(code)
            if not e:
                continue
            n = f"，{e['analysts']:.0f} 位分析師" if e.get("analysts") else ""
            lines.append(
                f"- 共識{ESTIMATE_PERIODS[code]}：EPS {_f(e['eps'])}（YoY {_pct(e.get('eps_growth'))}），"
                f"營收 {_money(e['revenue'], cur)}（{_unit(cur)}，YoY {_pct(e.get('revenue_growth'))}）{n}"
            )
        if not est:
            lines.append(f"- 共識預估：{NO_DATA}")
        nxt = fin.get("next_earnings") or f"{NO_DATA}（Yahoo 尚未公布下一次日期）"
        lines.append(f"- 下次財報日：{nxt}")
        if t in rec.valuations:
            lines += valuation_lines(rec.valuations[t], cur)
        lines.append("")
    return lines


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
