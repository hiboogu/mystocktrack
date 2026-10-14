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

## 自動化測試與部署

- `.github/workflows/ci.yml`：每次 push 與 PR 在 Python 3.11–3.13 跑 `ruff` 與 `pytest`。測試全部用合成資料，不連網、不呼叫 Claude。
- `.github/workflows/daily-report.yml`：美東收盤後（週一到五 UTC 22:30）自動執行，報告上傳為 artifact 並發佈到 GitHub Pages 的 `/report/`；原本的 `index.html`（Edge AI Portfolio Monitor）照樣放在網站首頁。也可在 Actions 頁手動觸發。

第一次啟用需要：
1. Settings → Secrets and variables → Actions → 新增 `ANTHROPIC_API_KEY`。
2. Settings → Pages → Source 選 **GitHub Actions**。
