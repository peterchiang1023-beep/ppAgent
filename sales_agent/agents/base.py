"""子 Agent 介面定義。

每個子 Agent 模組提供一個 build_spec(settings) -> SubAgentSpec，
主管 Agent 會把 implemented=True 的子 Agent 轉成 SDK 的 AgentDefinition 註冊。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from claude_agent_sdk import AgentDefinition


@dataclass
class SubAgentSpec:
    name: str
    description: str             # 給主管看的「何時使用」說明
    prompt: str                  # 子 Agent 的系統提示
    tools: list[str] = field(default_factory=list)
    model: str | None = None
    implemented: bool = True
    max_turns: int | None = None

    def to_definition(self) -> AgentDefinition:
        return AgentDefinition(
            description=self.description,
            prompt=self.prompt,
            tools=self.tools,
            model=self.model,
            maxTurns=self.max_turns,
        )


def skeleton_prompt(name: str, purpose: str) -> str:
    """骨架子 Agent 的提示：明確告知尚未實作，避免被誤用。"""
    return (
        f"你是 {name} 子 Agent（尚未實作）。預定職責：{purpose}\n"
        "目前只有骨架，請直接回覆「此功能尚未實作」，不要執行任何動作。"
    )
