"""核心層：主管 Agent。

負責：
- 組合 Claude Agent SDK 的選項（模型、系統提示、子 Agent、MCP 工具、權限、預算上限）
- Hooks：每次工具呼叫前後寫日誌、計算呼叫次數、強制安全規則
- 串流顯示執行過程，結束後累計成本
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
)
from rich.console import Console

from sales_agent.agents import all_specs
from sales_agent.config import Settings
from sales_agent.core.budget import BudgetTracker
from sales_agent.core.prompts import supervisor_system_prompt
from sales_agent.core.safety import (
    BLOCKED_BUILTIN_TOOLS,
    MCP_SERVER_NAME,
    evaluate_tool_call,
    redact_obj,
)
from sales_agent.logging_setup import get_logger, log_action
from sales_agent.profiles.loader import ProductProfile
from sales_agent.tools.context import ToolContext, set_context
from sales_agent.tools.registry import build_mcp_server, mcp_tool_name

logger = get_logger("supervisor")

# 自動允許（仍會經過 PreToolUse hook 的安全與預算檢查）
AUTO_ALLOWED_TOOLS = [
    "Agent",
    "Task",
    "WebSearch",
    "WebFetch",
    mcp_tool_name("get_product_profile"),
    mcp_tool_name("estimate_profit"),
    mcp_tool_name("save_report"),
    mcp_tool_name("get_budget_status"),
    mcp_tool_name("create_draft"),
]


@dataclass
class RunResult:
    run_id: str
    success: bool
    final_text: str = ""
    cost_usd: float = 0.0
    num_turns: int = 0
    reports: list[str] = field(default_factory=list)
    stopped_reason: str = ""


class Supervisor:
    def __init__(
        self,
        settings: Settings,
        profile: ProductProfile,
        budget: BudgetTracker,
        console: Console | None = None,
    ) -> None:
        self.settings = settings
        self.profile = profile
        self.budget = budget
        self.console = console or Console()
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.specs = all_specs(settings)
        self._stop_reason = ""
        self._reports: list[str] = []
        set_context(ToolContext(settings=settings, profile=profile, budget=budget, run_id=self.run_id))

    # ---------- 選項 ----------
    def build_options(self) -> ClaudeAgentOptions:
        enabled = [s for s in self.specs if s.implemented]
        disabled = [s.name for s in self.specs if not s.implemented]
        return ClaudeAgentOptions(
            model=self.settings.supervisor_model,
            system_prompt=supervisor_system_prompt([s.name for s in enabled], disabled),
            # 只開放必要的內建工具：子 Agent 委派與網路搜尋（不含命令列、檔案修改）
            tools=["Agent", "Task", "WebSearch", "WebFetch"],
            allowed_tools=AUTO_ALLOWED_TOOLS,
            disallowed_tools=sorted(BLOCKED_BUILTIN_TOOLS),
            mcp_servers={MCP_SERVER_NAME: build_mcp_server()},
            agents={s.name: s.to_definition() for s in enabled},
            can_use_tool=self._can_use_tool,
            hooks={
                "PreToolUse": [HookMatcher(matcher=None, hooks=[self._pre_tool_hook])],
                "PostToolUse": [HookMatcher(matcher=None, hooks=[self._post_tool_hook])],
            },
            max_turns=self.settings.max_turns,
            max_budget_usd=self.budget.run_budget(self.settings.run_budget_usd),
            cwd=str(self.settings.project_root),
            setting_sources=[],  # 不載入使用者本機的 Claude Code 設定，確保行為可重現
            env={"ANTHROPIC_API_KEY": self.settings.anthropic_api_key},
        )

    # ---------- 權限與 Hooks ----------
    async def _can_use_tool(
        self, tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        """不在自動允許清單的工具會來到這裡：依白名單判斷，預設拒絕。"""
        decision = evaluate_tool_call(tool_name, tool_input)
        log_action("permission_check", run_id=self.run_id, tool=tool_name,
                   allowed=decision.allowed, reason=decision.reason)
        if decision.allowed:
            return PermissionResultAllow()
        return PermissionResultDeny(message=decision.reason)

    async def _pre_tool_hook(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        agent = input_data.get("agent_type") or "supervisor"

        decision = evaluate_tool_call(tool_name, tool_input)
        if not decision.allowed:
            log_action("tool_denied", run_id=self.run_id, agent=agent, tool=tool_name,
                       reason=decision.reason, input=redact_obj(tool_input))
            self.console.print(f"[yellow]⛔ 已攔截 {tool_name}：{decision.reason}[/yellow]")
            return _deny(decision.reason)

        if not self.budget.register_tool_call(tool_name):
            self._stop_reason = f"今日工具呼叫次數已達上限（{self.budget.daily_tool_call_limit}），已停止執行"
            log_action("budget_alert", run_id=self.run_id, kind="daily_tool_calls", status=self.budget.status())
            self.console.print(f"[bold red]🛑 {self._stop_reason}[/bold red]")
            return {**_deny(self._stop_reason), "continue_": False, "stopReason": self._stop_reason}

        log_action("tool_call", run_id=self.run_id, agent=agent, tool=tool_name,
                   tool_use_id=tool_use_id, input=redact_obj(tool_input))
        return {}

    async def _post_tool_hook(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        tool_name = input_data.get("tool_name", "")
        response = input_data.get("tool_response")
        text = str(response)
        if tool_name == mcp_tool_name("save_report") and "報告已存檔：" in text:
            path = text.split("報告已存檔：", 1)[1].split("'")[0].split('"')[0].strip()
            self._reports.append(path)
        log_action("tool_result", run_id=self.run_id, agent=input_data.get("agent_type") or "supervisor",
                   tool=tool_name, tool_use_id=tool_use_id, response=redact_obj(text[:3000]))
        return {}

    # ---------- 執行 ----------
    async def run(self, task_prompt: str, task_name: str) -> RunResult:
        self.budget.check_can_start()
        self.budget.start_run()
        options = self.build_options()
        log_action("run_start", run_id=self.run_id, task=task_name, product=self.profile.product_name,
                   model=self.settings.supervisor_model, run_budget_usd=options.max_budget_usd,
                   budget=self.budget.status())
        self.console.print(
            f"[bold cyan]▶ 開始任務 {task_name}[/bold cyan]（執行編號 {self.run_id}，"
            f"本次預算上限 {options.max_budget_usd} USD）"
        )

        result = RunResult(run_id=self.run_id, success=False)
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(task_prompt)
                async for message in client.receive_response():
                    self._handle_message(message, result)
        except Exception as exc:
            logger.exception("執行失敗")
            log_action("run_error", run_id=self.run_id, error=repr(exc))
            result.stopped_reason = repr(exc)
            raise
        finally:
            result.reports = list(dict.fromkeys(self._reports))
            if self._stop_reason:
                result.stopped_reason = self._stop_reason
            log_action("run_end", run_id=self.run_id, success=result.success, cost_usd=result.cost_usd,
                       turns=result.num_turns, reports=result.reports, stopped=result.stopped_reason,
                       budget=self.budget.status())
        return result

    def _handle_message(self, message: Any, result: RunResult) -> None:
        if isinstance(message, SystemMessage) and message.subtype == "init":
            log_action("session_init", run_id=self.run_id,
                       tools=message.data.get("tools"), agents=message.data.get("agents"),
                       model=message.data.get("model"))
        elif isinstance(message, AssistantMessage):
            who = "子Agent" if message.parent_tool_use_id else "主管"
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    if not message.parent_tool_use_id:
                        self.console.print(f"[green]{who}[/green]：{block.text.strip()}")
                    log_action("assistant_text", run_id=self.run_id, by=who, text=block.text)
                elif isinstance(block, ToolUseBlock):
                    self.console.print(f"[dim]  ↳ {who} 呼叫 {block.name} {_brief(block.input)}[/dim]")
        elif isinstance(message, ResultMessage):
            result.cost_usd = message.total_cost_usd or 0.0
            result.num_turns = message.num_turns
            result.final_text = message.result or ""
            result.success = not message.is_error
            if message.is_error:
                result.stopped_reason = f"{message.subtype} {message.errors or ''}".strip()
                if message.subtype == "error_max_budget_usd":
                    result.stopped_reason = "已達本次執行預算上限，已停止"
                    log_action("budget_alert", run_id=self.run_id, kind="run_budget")
            self.budget.add_cost(message.total_cost_usd)


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _brief(tool_input: dict) -> str:
    for key in ("query", "url", "subagent_type", "market", "title"):
        if key in tool_input:
            return f"{key}={str(tool_input[key])[:80]}"
    return ""
