"""【骨架】社群發文工具 —— 供 social 子 Agent 使用。

只能透過官方 API（Instagram Graph API、TikTok Content Posting API）。
第一階段：只定義介面，不呼叫任何 API。發文與排程一律走草稿佇列。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class SocialPost:
    platform: str                # instagram / tiktok
    language: str
    caption: str
    hashtags: list[str] = field(default_factory=list)
    media_paths: list[str] = field(default_factory=list)
    scheduled_at: datetime | None = None


class SocialPublisher(Protocol):
    """社群平台發文介面。可抽換。"""

    def publish(self, post: SocialPost) -> str:
        """發布或排程貼文，回傳貼文 ID。僅能在草稿核准後由 executor 呼叫。"""
        ...


class InstagramGraphPublisher:
    def publish(self, post: SocialPost) -> str:
        # TODO: Instagram Graph API：建立 media container → media_publish；需商業帳號與 access token（.env）。
        raise NotImplementedError("第一階段不發文；請使用 create_draft 建立貼文草稿")


class TikTokPublisher:
    def publish(self, post: SocialPost) -> str:
        # TODO: TikTok Content Posting API（需通過 app 審核），支援排程與草稿上傳。
        raise NotImplementedError("第一階段不發文；請使用 create_draft 建立貼文草稿")
