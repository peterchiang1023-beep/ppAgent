"""CLI 任務 → 交給主管 Agent 的任務描述。"""

from __future__ import annotations

from sales_agent.profiles.loader import ProductProfile


def _market_note(profile: ProductProfile, market: str) -> str:
    m = profile.market(market)
    if m:
        return f"目標市場 {m.country}（語言 {', '.join(m.languages)}，幣別 {m.currency}，標準 VAT {m.vat_rate:.0%}）"
    return f"目標市場 {market}（不在設定檔 target_markets 中，請依一般歐盟規則並查證當地資訊）"


def research_task(profile: ProductProfile, market: str) -> str:
    return f"""\
任務：選品研究
產品：{profile.product_name}
{_market_note(profile, market)}

請規劃並分派給 research 子 Agent，完成此產品在 {market} 的選品研究報告
（市場趨勢、通路、競品、價格帶、評論痛點、利潤估算），報告必須附資料來源連結並以 save_report 存檔。
完成後向我總結報告路徑、關鍵發現、是否達到利潤底線 {profile.min_profit_margin:.0%}、建議下一步。"""


def compliance_task(profile: ProductProfile, market: str) -> str:
    return f"""\
任務：市場與法規整理
產品：{profile.product_name}
{_market_note(profile, market)}

請規劃並分派給 market_compliance 子 Agent，整理 {market} 的銷售通路、消費習慣，以及
CE、GPSR、EPR、VAT/OSS、品類特定法規與平台合規要求，並對照設定檔的認證文件清單列出缺口。
報告必須附資料來源連結並以 save_report 存檔。完成後向我總結報告路徑與最重要的待辦事項。"""


TASKS = {
    "research": research_task,
    "compliance": compliance_task,
}
