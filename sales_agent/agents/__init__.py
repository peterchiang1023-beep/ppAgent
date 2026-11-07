"""子 Agent 登錄。新增子 Agent：建立模組並加入 MODULES。"""

from __future__ import annotations

from sales_agent.config import Settings

from . import analytics, lead_gen, listing, market_compliance, research, social
from .base import SubAgentSpec

MODULES = [research, market_compliance, lead_gen, listing, social, analytics]


def all_specs(settings: Settings) -> list[SubAgentSpec]:
    return [m.build_spec(settings) for m in MODULES]
