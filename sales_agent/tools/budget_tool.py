"""工具：查詢今日預算與呼叫次數使用狀況。"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import tool

from .context import get_context, text_result


@tool(
    "get_budget_status",
    "查詢今日已用預算（USD）、剩餘預算與工具呼叫次數。",
    {"type": "object", "properties": {}},
    annotations={"readOnlyHint": True},
)
async def get_budget_status(args: dict[str, Any]) -> dict[str, Any]:
    budget = get_context().budget
    if budget is None:
        return text_result("預算追蹤器未啟用", is_error=True)
    return text_result(json.dumps(budget.status(), ensure_ascii=False, indent=2))
