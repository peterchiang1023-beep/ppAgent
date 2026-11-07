"""工具執行環境：讓各工具模組取得設定、產品設定檔與預算追蹤器。

工具是在同一個 Python 行程內執行的 MCP 工具，因此用模組層級的 context 傳遞狀態。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sales_agent.config import Settings
    from sales_agent.core.budget import BudgetTracker
    from sales_agent.profiles.loader import ProductProfile


@dataclass
class ToolContext:
    settings: "Settings"
    profile: "ProductProfile | None" = None
    budget: "BudgetTracker | None" = None
    run_id: str = ""


_context: ToolContext | None = None


def set_context(ctx: ToolContext) -> None:
    global _context
    _context = ctx


def get_context() -> ToolContext:
    if _context is None:
        raise RuntimeError("ToolContext 尚未初始化")
    return _context


def text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    """MCP 工具標準回傳格式。"""
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["is_error"] = True
    return result
