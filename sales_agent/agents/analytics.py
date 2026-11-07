"""【骨架】analytics 子 Agent：彙整銷售與社群數據，產出週報。

第一階段只定義介面，不呼叫任何外部 API。
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from sales_agent.config import Settings

from .base import SubAgentSpec, skeleton_prompt

NAME = "analytics"
PURPOSE = "彙整各通路銷售與社群數據，產出週報（reports/，report_type=analytics）"


class AnalyticsAgent(Protocol):
    def weekly_report(self, week_start: date) -> str:
        """產出週報 Markdown 並回傳檔案路徑。"""
        ...


class AnalyticsNotImplemented:
    def weekly_report(self, week_start: date) -> str:
        # TODO: 透過 tools/analytics_tool.py 的 MetricsSource 取得數據，計算 KPI（營收、毛利、ACoS、轉換率、
        #   互動率），與上週比較，用 save_report 存檔。
        raise NotImplementedError


def build_spec(settings: Settings) -> SubAgentSpec:
    return SubAgentSpec(
        name=NAME, description=PURPOSE, prompt=skeleton_prompt(NAME, PURPOSE),
        tools=[], model=settings.subagent_model, implemented=False,
    )
