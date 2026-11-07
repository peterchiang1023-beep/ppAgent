"""【骨架】Email 寄送工具 —— 供 lead_gen 子 Agent 使用。

第一階段：只定義介面，不連接任何郵件服務。寄信一律走草稿佇列。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class OutreachEmail:
    to_company: str
    to_role: str                 # GDPR：優先使用職稱／公司通用信箱，避免私人資料
    language: str
    subject: str
    body: str
    to_address: str = ""         # 僅在具合法利益（Legitimate Interest）時填寫
    unsubscribe_note: str = "如不希望再收到我們的訊息，請直接回覆告知，我們將立即刪除您的資料。"
    attachments: list[str] = field(default_factory=list)


class EmailProvider(Protocol):
    """郵件服務供應商介面（例如 SMTP、Gmail API、SendGrid）。可抽換。"""

    def send(self, email: OutreachEmail) -> str:
        """寄出信件並回傳訊息 ID。只能在草稿被人工核准後由 executor 呼叫。"""
        ...


class NotConfiguredEmailProvider:
    """預設實作：拒絕寄送。"""

    def send(self, email: OutreachEmail) -> str:
        # TODO: 實作官方郵件 API（例如 Gmail API / SendGrid），
        #   並加入退訂名單檢查、寄送頻率限制、GDPR 合法基礎紀錄。
        raise NotImplementedError("第一階段不寄送任何 Email；請使用 create_draft 建立草稿")
