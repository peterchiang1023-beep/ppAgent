"""工具登錄：把各工具模組組成同一個 in-process MCP server。

要抽換或新增工具，只需修改 ALL_TOOLS；子 Agent 依名稱取用。
"""

from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server

from sales_agent.core.safety import MCP_PREFIX, MCP_SERVER_NAME

from .budget_tool import get_budget_status
from .draft_tool import create_draft
from .profile_tool import get_product_profile
from .profit_tool import estimate_profit
from .report_tool import save_report

ALL_TOOLS = [get_product_profile, estimate_profit, save_report, create_draft, get_budget_status]


def build_mcp_server():
    return create_sdk_mcp_server(name=MCP_SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)


def mcp_tool_name(short: str) -> str:
    """save_report -> mcp__sales__save_report"""
    return MCP_PREFIX + short
