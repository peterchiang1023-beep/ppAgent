"""【骨架】電商平台上架工具 —— 供 listing 子 Agent 使用。

只能透過官方 API（Amazon SP-API、Allegro REST API、Kaufland Seller API 等），禁止爬蟲或模擬點擊。
第一階段：只定義介面，不呼叫任何 API。上架、改價一律走草稿佇列。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ListingContent:
    marketplace: str             # 例如 amazon_de、allegro_pl
    language: str
    title: str
    bullet_points: list[str]
    description: str
    search_terms: list[str] = field(default_factory=list)
    price_gross: float | None = None
    currency: str = "EUR"
    sku: str = ""
    gpsr_info: dict[str, str] = field(default_factory=dict)  # 製造商／歐盟責任人／安全資訊


class MarketplaceClient(Protocol):
    """平台 API 介面。可抽換。"""

    def submit_listing(self, listing: ListingContent) -> str:
        """送出上架，回傳平台提交編號。僅能在草稿核准後由 executor 呼叫。"""
        ...

    def update_price(self, sku: str, price_gross: float, currency: str) -> str:
        """改價。僅能在草稿核准後由 executor 呼叫。"""
        ...


class AmazonSPAPIClient:
    """Amazon Selling Partner API 用戶端（未實作）。"""

    def __init__(self) -> None:
        # TODO: 從 .env 讀取 SP_API_CLIENT_ID / SP_API_CLIENT_SECRET / SP_API_REFRESH_TOKEN，
        #   使用 LWA OAuth 取得 access token；使用官方 python-amazon-sp-api 或自行簽章。
        pass

    def submit_listing(self, listing: ListingContent) -> str:
        # TODO: 呼叫 Listings Items API（putListingsItem），先以 VALIDATION_PREVIEW 模式驗證。
        raise NotImplementedError("第一階段不呼叫 SP-API；請使用 create_draft 建立上架草稿")

    def update_price(self, sku: str, price_gross: float, currency: str) -> str:
        # TODO: 呼叫 Listings Items API（patchListingsItem）更新 purchasable_offer。
        raise NotImplementedError("第一階段不改價；請使用 create_draft 建立改價草稿")
