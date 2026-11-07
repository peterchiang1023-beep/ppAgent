"""【骨架】social 子 Agent：規劃 Instagram、TikTok 內容並排程發布。

第一階段只定義介面，不呼叫任何外部 API。
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from sales_agent.config import Settings
from sales_agent.tools.social_tool import SocialPost

from .base import SubAgentSpec, skeleton_prompt

NAME = "social"
PURPOSE = "規劃 Instagram、TikTok 內容行事曆與貼文，建立排程草稿，核准後透過官方 API 發布"


class SocialAgent(Protocol):
    def plan_calendar(self, country: str, start: date, weeks: int = 4) -> list[SocialPost]: ...


class SocialNotImplemented:
    def plan_calendar(self, country: str, start: date, weeks: int = 4) -> list[SocialPost]:
        # TODO: 依當地節慶、品牌語氣產生內容行事曆；每則貼文以 create_draft(action_type="social_post") 建立草稿。
        raise NotImplementedError


def build_spec(settings: Settings) -> SubAgentSpec:
    return SubAgentSpec(
        name=NAME, description=PURPOSE, prompt=skeleton_prompt(NAME, PURPOSE),
        tools=[], model=settings.subagent_model, implemented=False,
    )
