"""Portfolio disclosure calculated from the same frozen market snapshot."""
from __future__ import annotations

import tomllib
from pathlib import Path


def holdings_markdown(path, provider):
    config = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    lines = [
        "## 我的實際持倉（同一市場快照）", "",
        "| 股票 | 股數 | 平均成本 USD | 投入成本 USD | 快照價 USD | 未實現損益 USD | 報酬率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    total_cost = 0.0
    total_market = 0.0
    complete = True
    for position in config.get("positions", []):
        ticker = position["ticker"]
        quantity = float(position["quantity"])
        basis = float(position["avg_cost"])
        cost = quantity * basis
        total_cost += cost
        try:
            price = provider.snapshot(ticker).price
            market = price * quantity
            total_market += market
            gain = market - cost
            lines.append(
                f"| {ticker} | {quantity:g} | {basis:.4f} | {cost:.2f} | "
                f"{price:.2f} | {gain:+.2f} | {gain / cost:+.2%} |"
            )
        except (KeyError, ValueError):
            complete = False
            lines.append(
                f"| {ticker} | {quantity:g} | {basis:.4f} | {cost:.2f} | "
                "N/A | N/A | N/A |"
            )
    if complete and total_cost:
        lines += [
            "", f"**合計投入：USD {total_cost:,.2f}；快照市值：USD {total_market:,.2f}；"
            f"未實現損益：USD {total_market-total_cost:+,.2f} "
            f"({(total_market-total_cost)/total_cost:+.2%})**",
        ]
    else:
        lines += ["", f"**合計投入：USD {total_cost:,.2f}；部分價格無法取得，合計浮盈虧不顯示。**"]
    lines += ["", "> 成本不含費用及稅項；這是快照估值，不是券商即時持倉。", ""]
    return "\n".join(lines)
