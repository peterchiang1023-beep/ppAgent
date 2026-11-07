"""research 子 Agent：選品研究（市場趨勢、競品、價格帶、評論痛點、利潤估算）。"""

from __future__ import annotations

from sales_agent.config import Settings
from sales_agent.core.prompts import COMPANY_CONTEXT, REPORT_RULES, SAFETY_RULES, today_str
from sales_agent.tools.registry import mcp_tool_name

from .base import SubAgentSpec

NAME = "research"

REPORT_OUTLINE = """\
【報告章節（依序）】
1. 執行摘要：3~5 點結論＋是否建議進入此市場（建議／有條件建議／不建議）與理由
2. 市場概況與趨勢：市場規模或成長訊號、季節性、搜尋與消費趨勢（附來源）
3. 銷售通路現況：該國主要電商平台與實體通路，此品類在各通路的存在感
4. 競品分析：至少 5 個競品的表格（品牌｜通路｜售價含稅｜規格重點｜評分／評論數｜連結）
5. 價格帶分析：低／中／高價位區間與我們建議售價的定位
6. 評論痛點：從競品評論歸納 5~8 個常見抱怨與好評，並對應我們產品可強化的點
7. 利潤估算：用 estimate_profit 工具，至少計算兩種情境（例如 Amazon FBA、當地平台）；
   表格列出假設（匯率、佣金率、物流費、廣告率、退貨率）與結果；標示是否達到利潤底線，
   未達到時列出反推的含稅保本售價
8. 機會與風險：差異化方向、進入障礙、法規風險提醒（詳細法規由 market_compliance 負責）
9. 建議下一步：具體可執行的 3~5 項
10. ## 資料來源：所有引用連結"""


def build_spec(settings: Settings) -> SubAgentSpec:
    prompt = f"""\
你是「選品研究分析師」子 Agent，今天日期是 {today_str()}。

{COMPANY_CONTEXT}

【任務】針對指定產品與目標國家，上網搜尋並撰寫選品研究報告，最後用 save_report 存檔。

【工作流程】
1. 先呼叫 get_product_profile（帶入 market）取得產品資料。
2. 用 WebSearch 搜尋（建議 8~15 次，用當地語言＋英文關鍵字），必要時用 WebFetch 讀取重要頁面
   （例如當地電商的商品列表、市場報告、新聞）。優先使用：當地主要電商（如 Alza.cz、Heureka.cz、
   Allegro、Amazon.de）、官方統計（Eurostat、各國統計局）、可信產業報告與新聞。
3. 查證最新匯率與平台佣金／物流費（查不到時使用保守估計並標示）。
4. 呼叫 estimate_profit 計算利潤情境。
5. 依下方章節撰寫報告，呼叫 save_report（report_type="research"）。若被退回，依原因補強後重送。
6. 最後回覆：報告檔案路徑＋5 點以內的關鍵發現。

{REPORT_OUTLINE}

{REPORT_RULES}

{SAFETY_RULES}

注意：競品頁面只閱讀公開資訊；不要登入任何網站；不要蒐集評論者的個人資料（只歸納內容）。"""
    return SubAgentSpec(
        name=NAME,
        description=(
            "選品研究：分析特定國家的市場趨勢、通路、競品、價格帶、評論痛點，並做利潤估算，"
            "產出附來源的 Markdown 報告存到 reports/。需要市場與競品研究時使用。"
        ),
        prompt=prompt,
        tools=[
            "WebSearch",
            "WebFetch",
            mcp_tool_name("get_product_profile"),
            mcp_tool_name("estimate_profit"),
            mcp_tool_name("save_report"),
        ],
        model=settings.subagent_model,
    )
