"""【骨架】數據彙整工具 —— 供 analytics 子 Agent 使用。

第一階段：只定義介面，不連接任何數據來源。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class SalesMetrics:
    channel: str
    period_start: date
    period_end: date
    units_sold: int = 0
    revenue_gross: float = 0.0
    currency: str = "EUR"
    ad_spend: float = 0.0
    returns: int = 0
    extra: dict[str, float] = field(default_factory=dict)


@dataclass
class SocialMetrics:
    platform: str
    period_start: date
    period_end: date
    followers: int = 0
    impressions: int = 0
    engagement_rate: float = 0.0


class MetricsSource(Protocol):
    """數據來源介面（Amazon SP-API Reports、Shopify Admin API、IG Insights 等）。可抽換。"""

    def fetch_sales(self, start: date, end: date) -> list[SalesMetrics]: ...

    def fetch_social(self, start: date, end: date) -> list[SocialMetrics]: ...


class NotConfiguredMetricsSource:
    def fetch_sales(self, start: date, end: date) -> list[SalesMetrics]:
        # TODO: Amazon SP-API Reports API（GET_SALES_AND_TRAFFIC_REPORT）、Shopify Admin API 等。
        raise NotImplementedError("第一階段未連接銷售數據來源")

    def fetch_social(self, start: date, end: date) -> list[SocialMetrics]:
        # TODO: Instagram Insights API、TikTok Research / Business API。
        raise NotImplementedError("第一階段未連接社群數據來源")
