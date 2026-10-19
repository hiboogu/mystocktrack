# mystocktrack

AI edge device stock track

一個「投資組合經理」主導 agent 帶領 4 個角色 agent，彼此傳訊息、互相質疑，最後產出投資建議報告。
偏好設定：**美股長期配置**、**比特幣相關資產短線進出**。

> 本專案產出的內容僅供研究與教育用途，不構成任何投資建議。

## 角色與溝通流程

| 角色 | 負責 |
|---|---|
| 投資組合經理（主導） | 指派任務、主持辯論、依風控上限決定配置並寫摘要 |
| 基本面／估值分析師 | 本益比、PEG、ROE、淨利率、營收成長、負債、自由現金流，判斷是否值得長抱 |
| 總經與市場情緒分析師 | S&P 500 趨勢、VIX、十年期殖利率、個股動能 |
| 比特幣短線交易員 | 均線交叉、RSI、波動度，給進場、停損、停利價位 |
| 風控經理 | 波動與回撤檢查，質疑過度樂觀的看法，設定單一部位與加密部位上限 |

所有訊息都經過同一條訊息匯流排（`bus.py`），報告最後會附上完整對話紀錄：

```
經理 ──指派──▶ 各分析師
各分析師 ──報告──▶ 經理
風控 ──質疑──▶ 對高風險資產過度看多的分析師
分析師 ──回應──▶ 風控（維持或下修）
風控 ──部位上限──▶ 經理
經理 ──裁決──▶ 全體
```

每個角色先用規則引擎算出初稿；有設定 `ANTHROPIC_API_KEY` 時，再交給 Claude（預設 `claude-opus-5-5`）依證據修正分數、回應質疑，並由經理寫出白話摘要。沒有金鑰時整套系統仍可用規則引擎跑完。

架構參考 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（分析師、辯論、風控、經理拍板）與 [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) 的價值／品質投資觀點，程式碼為自行撰寫。

## 使用方式

```bash
pip install -e ".[dev,site]"
export ANTHROPIC_API_KEY=...        # 可省略，省略時只用規則引擎
mystocktrack run                    # 報告寫到 reports/
mystocktrack run --offline          # 強制不呼叫 Claude
```

觀察清單、目前持股（成本與股數）與風控門檻都在 `watchlist.toml` 修改。有填持股時，報告會多一段「我的持股檢視」，列出每檔的未實現損益，以及續抱、可加碼、減碼或停損出場的建議與停損參考價。

刻意的題材投機可以在持股加上 `speculative = true`（可再填 `catalyst` 與 `review_by`）。這類持股不依長期基本面規則出場，只看三件事：占持股總值是否超過 `speculative_max_weight`、虧損是否達到 `speculative_max_loss` 的硬停損、檢討日是否已過。

日股可以直接加進 `tickers`，用東京證交所代號加 `.T`（例如 Lasertec 是 `6920.T`），也可以在 `[names]` 幫代號取顯示名稱。日股的價格與金額都以日圓計；有日股時，總經分析師會改看日經 225 與美元兌日圓匯率，並說明匯率對以美元計報酬的影響。

報告的「財報與預期」段落列出每檔股票最近 3 個會計年度的營收、每股營收、EPS、自由現金流與資本支出，最近一季 EPS 對共識的差異與連續優於／低於共識的季數，本季、本年度與下一年度的共識預估，以及下次財報日。資料來自 Yahoo Finance；Yahoo 沒有的項目會寫「資料不足」，財報日請以公司公告為準。

## 自動化測試與部署

- `.github/workflows/ci.yml`：每次 push 與 PR 在 Python 3.11–3.13 跑 `ruff` 與 `pytest`。測試全部用合成資料，不連網、不呼叫 Claude。
- `.github/workflows/daily-report.yml`：美東收盤後（週一到五 UTC 22:30）自動執行，報告上傳為 artifact 並發佈到 GitHub Pages 的 `/report/`；原本的 `index.html`（Edge AI Portfolio Monitor）照樣放在網站首頁。也可在 Actions 頁手動觸發。

第一次啟用需要：
1. Settings → Secrets and variables → Actions → 新增 `ANTHROPIC_API_KEY`。
2. Settings → Pages → Source 選 **GitHub Actions**。
