"""【骨架】listing 子 Agent：產生多語系商品文案，透過 Amazon SP-API 等官方 API 上架。

第一階段只定義介面，不呼叫任何外部 API。
"""

from __future__ import annotations

from typing import Protocol

from sales_agent.config import Settings
from sales_agent.tools.marketplace_tool import ListingContent

from .base import SubAgentSpec, skeleton_prompt

NAME = "listing"
PURPOSE = "產生多語系商品文案（遵守品牌語氣與禁用字詞），準備上架草稿，核准後透過官方 API 上架"


class ListingAgent(Protocol):
    def generate_listing(self, marketplace: str, language: str) -> ListingContent: ...

    def check_compliance(self, listing: ListingContent) -> list[str]:
        """檢查禁用字詞、GPSR 必要資訊、字數限制，回傳問題清單。"""
        ...


class ListingNotImplemented:
    def generate_listing(self, marketplace: str, language: str) -> ListingContent:
        # TODO: 依 profile 產生標題、五點描述、說明、關鍵字；各平台字數規則；
        #   完成後以 create_draft(action_type="listing") 進入草稿佇列。
        raise NotImplementedError

    def check_compliance(self, listing: ListingContent) -> list[str]:
        # TODO: 用 ProductProfile.find_banned_words 檢查，並確認 GPSR 製造商／歐盟責任人資訊。
        raise NotImplementedError


def build_spec(settings: Settings) -> SubAgentSpec:
    return SubAgentSpec(
        name=NAME, description=PURPOSE, prompt=skeleton_prompt(NAME, PURPOSE),
        tools=[], model=settings.subagent_model, implemented=False,
    )
