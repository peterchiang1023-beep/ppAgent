"""【骨架】lead_gen 子 Agent：找出歐洲經銷商、零售商、B2B 買家，撰寫個人化開發信。

第一階段只定義介面，不呼叫任何外部 API。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sales_agent.config import Settings
from sales_agent.tools.email_tool import OutreachEmail

from .base import SubAgentSpec, skeleton_prompt

NAME = "lead_gen"
PURPOSE = "找出歐洲經銷商、零售商、B2B 買家，撰寫個人化開發信（只建立草稿，不寄出）"


@dataclass
class Lead:
    """潛在客戶（以公司層級資訊為主，符合 GDPR 資料最小化）。"""

    company: str
    country: str
    website: str
    segment: str                       # distributor / retailer / b2b_buyer
    source_url: str                    # 資料來源（公開頁面）
    contact_role: str = ""             # 例如 Purchasing Manager
    generic_email: str = ""            # 例如 info@ / sales@（公司通用信箱）
    fit_score: float = 0.0
    notes: str = ""
    lawful_basis: str = "legitimate_interest"  # GDPR 合法基礎
    tags: list[str] = field(default_factory=list)


class LeadGenAgent(Protocol):
    def find_leads(self, country: str, segment: str, limit: int = 20) -> list[Lead]: ...

    def draft_outreach(self, lead: Lead, language: str) -> OutreachEmail: ...


class LeadGenNotImplemented:
    def find_leads(self, country: str, segment: str, limit: int = 20) -> list[Lead]:
        # TODO: 使用公開資料來源（商會名錄、展覽參展商名單、官方 B2B 資料庫 API）搜尋；
        #   禁止爬取需登入的平台（如 LinkedIn）；記錄每筆資料來源與合法基礎。
        raise NotImplementedError

    def draft_outreach(self, lead: Lead, language: str) -> OutreachEmail:
        # TODO: 依品牌語氣、禁用字詞、當地語言產生個人化信件，透過 create_draft 進入草稿佇列；
        #   信末附退訂說明與資料來源告知（GDPR 第 14 條）。
        raise NotImplementedError


def build_spec(settings: Settings) -> SubAgentSpec:
    return SubAgentSpec(
        name=NAME, description=PURPOSE, prompt=skeleton_prompt(NAME, PURPOSE),
        tools=[], model=settings.subagent_model, implemented=False,
    )
