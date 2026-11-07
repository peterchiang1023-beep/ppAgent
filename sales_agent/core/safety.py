"""安全規則的程式邏輯（與系統提示中的文字規則互相對應）。

1. 草稿模式：寄信、上架、發文、付款、改價只能建立草稿，需人工確認才執行。
2. 預算上限：見 budget.py，於 hooks 中強制執行。
3. 只用官方 API：禁止命令列、瀏覽器自動化，禁止抓取賣家後台網址。
4. GDPR：日誌中的個人資料（Email、電話）自動遮罩。

工具權限採「白名單、預設拒絕」：不在白名單內的工具一律拒絕。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

MCP_SERVER_NAME = "sales"
MCP_PREFIX = f"mcp__{MCP_SERVER_NAME}__"

# 子 Agent 委派工具（新版 CLI 名稱為 Agent，舊版為 Task）
DELEGATION_TOOLS = {"Agent", "Task"}
# 內建的網路工具（只讀取公開網頁）
WEB_TOOLS = {"WebSearch", "WebFetch"}

# 自訂工具白名單（皆為唯讀或只寫入本機報告／草稿）
SAFE_CUSTOM_TOOLS = {
    "get_product_profile",
    "estimate_profit",
    "save_report",
    "create_draft",
    "get_budget_status",
}

# 明確禁止的內建工具：命令列、檔案修改、瀏覽器自動化等
BLOCKED_BUILTIN_TOOLS = {
    "Bash", "BashOutput", "KillShell", "Write", "Edit", "MultiEdit",
    "NotebookEdit", "Computer", "Monitor",
}

# 會產生對外效果的動作關鍵字：這類工具永遠不可直接執行，只能經由 create_draft
EXTERNAL_ACTION_PATTERNS = re.compile(
    r"(send|email|mail|publish|post|upload|list_product|submit|pay|payment|charge|"
    r"refund|price|reprice|order|purchase|schedule_post)",
    re.IGNORECASE,
)

# 草稿可記錄的動作類型
DRAFT_ACTION_TYPES = ("email", "listing", "social_post", "payment", "price_change")

# 賣家後台與需登入的管理介面：禁止以 WebFetch 抓取（應改用官方 API）
BLOCKED_URL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(^|\.)sellercentral(-europe)?\.amazon\.",
        r"(^|\.)vendorcentral\.amazon\.",
        r"(^|\.)advertising\.amazon\.",
        r"(^|\.)seller\.(tiktok|tiktokglobalshop)\.com$",
        r"(^|\.)seller-[a-z]+\.tiktok\.com$",
        r"(^|\.)business\.facebook\.com$",
        r"(^|\.)partners?\.(alza|mall|allegro|kaufland)\.",
        r"(^|\.)admin\.shopify\.com$",
        r"(^|\.)myshopify\.com$",
    )
]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


def custom_tool_name(full_name: str) -> str | None:
    """mcp__sales__save_report -> save_report；非本專案 MCP 工具回傳 None。"""
    return full_name[len(MCP_PREFIX):] if full_name.startswith(MCP_PREFIX) else None


def is_blocked_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return True
    if parsed.scheme not in ("http", "https"):
        return True
    host = (parsed.hostname or "").lower()
    return any(p.search(host) for p in BLOCKED_URL_PATTERNS)


def evaluate_tool_call(tool_name: str, tool_input: dict | None = None) -> Decision:
    """判斷工具呼叫是否允許（白名單、預設拒絕）。"""
    tool_input = tool_input or {}

    if tool_name in BLOCKED_BUILTIN_TOOLS:
        return Decision(False, f"安全規則：禁止使用 {tool_name}（只能透過官方 API 與指定工具操作）")

    if tool_name in DELEGATION_TOOLS:
        return Decision(True)

    if tool_name in WEB_TOOLS:
        url = tool_input.get("url")
        if tool_name == "WebFetch" and url and is_blocked_url(url):
            return Decision(False, f"安全規則：禁止抓取賣家後台或管理介面（{url}），請改用官方 API")
        return Decision(True)

    short = custom_tool_name(tool_name)
    if short is not None:
        if short in SAFE_CUSTOM_TOOLS:
            if short == "create_draft" and tool_input.get("action_type") not in DRAFT_ACTION_TYPES:
                return Decision(False, f"草稿類型必須是 {DRAFT_ACTION_TYPES} 之一")
            return Decision(True)
        if EXTERNAL_ACTION_PATTERNS.search(short):
            return Decision(False, f"草稿模式：{short} 屬對外動作，只能用 create_draft 建立草稿並等待人工確認")
        return Decision(False, f"工具 {short} 不在白名單內")

    if tool_name.startswith("mcp__"):
        return Decision(False, f"安全規則：未授權的外部 MCP 工具 {tool_name}（禁止瀏覽器自動化／模擬點擊）")

    return Decision(False, f"工具 {tool_name} 不在白名單內")


# ---- GDPR：個人資料遮罩 ----
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<![\w/])\+?\d[\d\s().-]{7,}\d(?![\w/])")


def redact_pii(text: str) -> str:
    """遮罩 Email 與電話號碼，用於日誌與草稿摘要（資料最小化原則）。"""
    if not isinstance(text, str):
        return text
    text = _EMAIL_RE.sub("[EMAIL]", text)
    return _PHONE_RE.sub("[PHONE]", text)


def redact_obj(obj):
    """遞迴遮罩 dict / list 中的字串。"""
    if isinstance(obj, str):
        return redact_pii(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj
