"""工具：讀取目前載入的產品設定檔。"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import tool

from .context import get_context, text_result


@tool(
    "get_product_profile",
    "取得目前產品設定檔（名稱、規格、成本、售價、MOQ、目標市場、通路、品牌語氣、禁用字詞、認證、利潤底線）。"
    "可選擇傳入 market（國碼）只取該市場資訊。",
    {
        "type": "object",
        "properties": {"market": {"type": "string", "description": "ISO 國碼，例如 CZ"}},
    },
    annotations={"readOnlyHint": True},
)
async def get_product_profile(args: dict[str, Any]) -> dict[str, Any]:
    profile = get_context().profile
    if profile is None:
        return text_result("尚未載入產品設定檔", is_error=True)
    text = profile.to_prompt_context()
    market = (args.get("market") or "").strip()
    if market:
        m = profile.market(market)
        if m is None:
            text += f"\n\n注意：設定檔的 target_markets 中沒有 {market.upper()}，請以一般歐盟規則研究並在報告中註明。"
        else:
            text += "\n\n目前聚焦市場：" + json.dumps(m.model_dump(), ensure_ascii=False)
    return text_result(text)
