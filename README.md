# 通用銷售 AI Agent（ppAgent）

以 [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/) 開發的銷售 Agent，協助把中國工廠的產品從美國 Amazon 擴展到捷克與歐洲市場。
目前為**第一階段**：完成主管 Agent，以及可上網搜尋並產出報告的 `research`（選品研究）與 `market_compliance`（市場與法規）兩個子 Agent。

## 架構（三層設計）

```
main.py (CLI)
  │
  ▼
核心層  sales_agent/core/
  supervisor.py   主管 Agent：理解任務、規劃、透過 Agent 工具分派給子 Agent、驗收
  prompts.py      系統提示（含安全規則）
  safety.py       工具白名單（預設拒絕）、草稿模式、禁止抓取賣家後台、GDPR 個資遮罩
  budget.py       每日預算／呼叫次數追蹤，超過即停止
  │
  ├─ 子 Agent  sales_agent/agents/
  │    research ✅ / market_compliance ✅ / lead_gen 🚧 / listing 🚧 / social 🚧 / analytics 🚧
  │
工具層  sales_agent/tools/   （@tool + create_sdk_mcp_server，可抽換）
  profile_tool    讀取產品設定
  profit_tool     利潤估算（VAT、關稅、佣金、物流、廣告、退貨、保本價）
  report_tool     存 Markdown 報告並檢查來源連結
  draft_tool      草稿佇列（對外動作只能建立草稿）
  budget_tool     查詢預算
  email_tool / marketplace_tool / social_tool / analytics_tool  🚧 骨架（不呼叫外部 API）
  ＋ SDK 內建 WebSearch / WebFetch 上網搜尋
  │
客製化層  profiles/*.yaml   換產品只需換設定檔
```

輸出：`reports/`（報告）、`drafts/`（待確認草稿）、`logs/`（日誌與用量）。

## 安裝

需求：macOS / Linux、Python 3.12 以上。建議使用 [uv](https://docs.astral.sh/uv/)。

```bash
# 1. 安裝 uv（若尚未安裝）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安裝相依套件（uv 會自動下載 Python 3.12 並建立 .venv）
uv sync
```

不用 uv 也可以：

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio
```

## 設定金鑰

```bash
cp .env.example .env
# 編輯 .env，填入 ANTHROPIC_API_KEY（到 https://console.anthropic.com/ 取得）
```

`.env` 已列入 `.gitignore`，**請勿提交**。其他可調整項目：

| 變數 | 預設 | 說明 |
|---|---|---|
| `SUPERVISOR_MODEL` | `claude-opus-5-5` | 主管 Agent 模型 |
| `SUBAGENT_MODEL` | `claude-sonnet-5-5` | 子 Agent 模型 |
| `DAILY_BUDGET_USD` | `5` | 每日預算上限（美元） |
| `DAILY_TOOL_CALL_LIMIT` | `300` | 每日工具呼叫次數上限 |
| `RUN_BUDGET_USD` | `2` | 單次執行預算上限 |
| `MAX_TURNS` | `60` | 單次執行最多回合 |
| `MIN_REPORT_SOURCES` | `5` | 報告最少來源連結數 |

## 執行範例

```bash
# 選品研究（捷克）
uv run python main.py research --profile profiles/example.yaml --market CZ

# 市場與法規（德國）
uv run python main.py compliance --profile profiles/example.yaml --market DE

# 查看今日預算使用量
uv run python main.py budget

# 草稿佇列（人工確認對外動作）
uv run python main.py drafts list --status pending
uv run python main.py drafts show <草稿編號>
uv run python main.py drafts approve <草稿編號> --note "已確認"
uv run python main.py drafts reject  <草稿編號> --note "語氣需調整"
```

已啟用 venv 時可省略 `uv run`。每次研究約使用 10~20 次網路搜尋，成本依模型與搜尋量而定（Claude 網路搜尋另計費），可用 `main.py budget` 查看。

## 換產品

複製 `profiles/example.yaml` 修改即可。欄位：

- `product_name`、`category`、`description`、`specs`（規格，自由欄位）
- `cost`：`unit_cost`、`packaging_cost`、`shipping_to_eu_per_unit`、`duty_rate`
- `suggested_retail_price`（各幣別含稅售價）、`moq`
- `target_markets`：國碼、語言、幣別、VAT 稅率
- `target_channels`、`brand_voice`、`banned_words`、`certifications`
- `min_profit_margin`（利潤底線，淨利率 0~1）

載入時會用 pydantic 驗證，欄位錯誤會直接提示。

## 安全機制

| 規則 | 提示層 | 程式強制 |
|---|---|---|
| 草稿模式：寄信、上架、發文、付款、改價需人工確認 | 系統提示 | `safety.py` 攔截對外動作類工具；只能經 `create_draft` 進 `drafts/`；`main.py drafts approve` 人工核准（第一階段核准後不執行任何外部動作） |
| 每日 API 呼叫次數與預算上限 | 系統提示 | `budget.py` 跨次累計；PreToolUse hook 計數，超過即中止；SDK `max_budget_usd` 限制單次花費；超過時終端機紅字＋`logs/` 記錄 |
| 只用官方 API、不爬賣家後台 | 系統提示 | 工具白名單、預設拒絕；禁用 Bash／檔案修改／瀏覽器自動化 MCP；WebFetch 擋 Seller Central、TikTok Seller、Shopify 後台等網址 |
| GDPR | 系統提示 | 日誌與草稿摘要自動遮罩 Email／電話；lead_gen 介面以公司層級資料與合法基礎欄位設計 |

此外設定 `setting_sources=[]`，不載入本機 Claude Code 設定，確保行為可重現。

## 日誌

- `logs/agent_YYYYMMDD.log`：文字日誌
- `logs/actions_YYYYMMDD.jsonl`：每一次工具呼叫、攔截、子 Agent 輸出、報告存檔、預算警示（JSON Lines）
- `logs/usage_YYYYMMDD.json`：當日成本與呼叫次數

## 測試

```bash
uv run pytest
```

測試涵蓋設定檔驗證、利潤計算、報告驗證、預算上限、安全白名單、草稿佇列、骨架模組不呼叫外部 API、主管 Agent 選項與 hook。測試不會呼叫 Claude API。

## 後續階段（TODO）

- `lead_gen`：公開名錄／展覽名單搜尋潛在客戶，產生個人化開發信草稿
- `listing`：多語系文案、Amazon SP-API 上架（先 VALIDATION_PREVIEW）
- `social`：IG／TikTok 內容行事曆與排程草稿
- `analytics`：銷售與社群 KPI 週報
- 草稿核准後的 executor、Email／Slack 預算通知
