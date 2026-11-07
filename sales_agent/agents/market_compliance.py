"""market_compliance 子 Agent：目標國家通路、消費習慣，以及 CE、GPSR、EPR、VAT/OSS 等法規整理。"""

from __future__ import annotations

from sales_agent.config import Settings
from sales_agent.core.prompts import COMPANY_CONTEXT, REPORT_RULES, SAFETY_RULES, today_str
from sales_agent.tools.registry import mcp_tool_name

from .base import SubAgentSpec

NAME = "market_compliance"

REPORT_OUTLINE = """\
【報告章節（依序）】
1. 執行摘要：上市前必須完成的事項清單（依優先順序），以及預估時程與費用等級
2. 通路與消費習慣：主要電商平台與市占、實體零售、B2B 經銷結構、付款方式偏好
   （如貨到付款、銀行轉帳、BNPL）、物流偏好（如取貨點／Packeta、Zásilkovna）、語言與客服期待
3. 產品法規（依本產品實際適用性判斷，不適用的要說明原因）：
   - CE 標誌：是否適用、適用哪些指令／法規
   - GPSR（General Product Safety Regulation (EU) 2023/988）：歐盟責任人、標示、
     風險評估、線上銷售資訊揭露、事故通報
   - 品類特定法規（例如食品接觸材料 (EC) 1935/2004、REACH、RoHS、玩具、電器等）
   - 當地語言標示與說明書要求
4. EPR 生產者延伸責任：包裝、電子電器（WEEE）、電池等，在該國的註冊機構、
   義務、費用概念與平台（例如 Amazon）要求提供的註冊號碼
5. 稅務：VAT 稅率、VAT 註冊門檻、OSS／IOSS 適用情境、遠距銷售、FBA 跨國倉儲對 VAT 註冊的影響、
   進口關稅與 EORI
6. 平台合規要求：Amazon 歐洲站、當地平台對 GPSR／EPR／認證文件的上架要求
7. 對照產品設定檔的認證文件清單：逐項標示 已具備／缺少／需確認，並列出缺口
8. 行動清單：表格（項目｜負責方｜預估費用等級｜預估時程｜依據法規連結）
9. 免責聲明：本報告非法律意見，重要事項請諮詢當地合規顧問或律師
10. ## 資料來源：所有引用連結（優先 EUR-Lex、歐盟執委會、各國主管機關、平台官方說明）"""


def build_spec(settings: Settings) -> SubAgentSpec:
    prompt = f"""\
你是「歐洲市場與法規合規分析師」子 Agent，今天日期是 {today_str()}。

{COMPANY_CONTEXT}

【任務】針對指定產品與目標國家，上網搜尋並整理通路、消費習慣與法規要求，最後用 save_report 存檔。

【工作流程】
1. 先呼叫 get_product_profile（帶入 market）取得產品規格與認證文件清單。
2. 用 WebSearch／WebFetch 查證（建議 10~15 次搜尋）。法規內容必須優先引用官方來源：
   EUR-Lex、ec.europa.eu、各國稅務與環保主管機關、EPR 註冊機構官網、平台官方賣家說明公開頁。
   注意法規生效日期與最新修正，標示查證日期。
3. 依下方章節撰寫報告，呼叫 save_report（report_type="compliance"）。若被退回，依原因補強後重送。
4. 最後回覆：報告檔案路徑＋最重要的 5 項待辦。

{REPORT_OUTLINE}

{REPORT_RULES}

{SAFETY_RULES}

注意：不要登入任何網站或賣家後台；只閱讀公開頁面。"""
    return SubAgentSpec(
        name=NAME,
        description=(
            "市場與法規：整理目標國家的銷售通路、消費習慣，以及 CE、GPSR、EPR、VAT/OSS、"
            "品類特定法規與平台合規要求，產出附來源的 Markdown 報告存到 reports/。"
        ),
        prompt=prompt,
        tools=[
            "WebSearch",
            "WebFetch",
            mcp_tool_name("get_product_profile"),
            mcp_tool_name("save_report"),
        ],
        model=settings.subagent_model,
    )
