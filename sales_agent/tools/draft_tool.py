"""草稿佇列：所有對外動作（寄信、上架、發文、付款、改價）只能先建立草稿。

草稿存在 drafts/<id>.json，狀態：pending → approved / rejected。
人工以 `python main.py drafts approve <id>` 確認。第一階段核准後只標記狀態，
實際執行器（executor）尚未實作，不會呼叫任何外部 API。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from sales_agent.core.safety import DRAFT_ACTION_TYPES, redact_pii
from sales_agent.logging_setup import log_action

from .context import get_context, text_result

STATUSES = ("pending", "approved", "rejected")


@dataclass
class Draft:
    id: str
    action_type: str
    channel: str
    summary: str
    payload: dict[str, Any]
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: str | None = None
    reviewer_note: str = ""
    run_id: str = ""


class DraftQueue:
    def __init__(self, drafts_dir: Path) -> None:
        self.dir = drafts_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, draft_id: str) -> Path:
        if not draft_id.replace("-", "").isalnum():
            raise ValueError("草稿編號格式錯誤")
        return self.dir / f"{draft_id}.json"

    def _write(self, d: Draft) -> None:
        self._path(d.id).write_text(json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, action_type: str, channel: str, summary: str, payload: dict, run_id: str = "") -> Draft:
        if action_type not in DRAFT_ACTION_TYPES:
            raise ValueError(f"action_type 必須是 {DRAFT_ACTION_TYPES} 之一")
        d = Draft(
            id=datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8],
            action_type=action_type,
            channel=channel,
            summary=summary,
            payload=payload,
            run_id=run_id,
        )
        self._write(d)
        log_action("draft_created", draft_id=d.id, action_type=action_type,
                   channel=channel, summary=redact_pii(summary))
        return d

    def get(self, draft_id: str) -> Draft:
        path = self._path(draft_id)
        if not path.is_file():
            raise FileNotFoundError(f"找不到草稿 {draft_id}")
        return Draft(**json.loads(path.read_text(encoding="utf-8")))

    def list(self, status: str | None = None) -> list[Draft]:
        drafts = [Draft(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.dir.glob("*.json"))]
        return [d for d in drafts if status is None or d.status == status]

    def set_status(self, draft_id: str, status: str, note: str = "") -> Draft:
        if status not in STATUSES:
            raise ValueError(f"status 必須是 {STATUSES} 之一")
        d = self.get(draft_id)
        if d.status != "pending":
            raise ValueError(f"草稿 {draft_id} 已是 {d.status}，不可重複審核")
        d.status = status
        d.reviewed_at = datetime.now(timezone.utc).isoformat()
        d.reviewer_note = note
        self._write(d)
        log_action("draft_reviewed", draft_id=draft_id, status=status, note=note)
        # TODO（後續階段）：status == "approved" 時，交由對應的 executor（email / listing / social）
        #   透過官方 API 執行，並把執行結果寫回草稿。第一階段刻意不執行任何外部動作。
        return d


@tool(
    "create_draft",
    "建立一筆待人工確認的草稿。任何寄信、上架、發文、付款、改價都只能用這個工具，不會實際執行。",
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": list(DRAFT_ACTION_TYPES)},
            "channel": {"type": "string", "description": "例如 email、amazon_de、instagram"},
            "summary": {"type": "string", "description": "一句話說明這個動作"},
            "payload": {"type": "object", "description": "動作內容（信件內文、商品文案、貼文等）"},
        },
        "required": ["action_type", "channel", "summary", "payload"],
    },
)
async def create_draft(args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_context()
    try:
        d = DraftQueue(ctx.settings.drafts_dir).create(
            args["action_type"], args["channel"], args["summary"], args.get("payload") or {}, ctx.run_id
        )
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(f"已建立草稿 {d.id}（狀態：pending），需人工執行 `python main.py drafts approve {d.id}` 確認。")
