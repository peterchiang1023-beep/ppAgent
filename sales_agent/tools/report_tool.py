"""工具：把報告存成 Markdown（reports/），並檢查是否附上足夠的資料來源連結。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

from sales_agent.logging_setup import log_action

from .context import get_context, text_result

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
SOURCES_HEADING_RE = re.compile(r"^#{1,3}\s*(資料來源|參考資料|Sources|References)\s*$", re.MULTILINE)
REPORT_TYPES = ("research", "compliance", "lead_gen", "listing", "social", "analytics")


class ReportValidationError(ValueError):
    pass


def extract_urls(markdown: str) -> list[str]:
    """擷取不重複的 URL（保留順序）。"""
    seen: dict[str, None] = {}
    for url in URL_RE.findall(markdown):
        seen.setdefault(url.rstrip(".,;:"), None)
    return list(seen)


def validate_report(markdown: str, min_sources: int) -> list[str]:
    """驗證報告；通過則回傳來源 URL 清單，否則丟出 ReportValidationError。"""
    problems = []
    urls = extract_urls(markdown)
    if len(urls) < min_sources:
        problems.append(f"資料來源連結只有 {len(urls)} 個，至少需要 {min_sources} 個")
    if not SOURCES_HEADING_RE.search(markdown):
        problems.append("缺少「## 資料來源」章節")
    if problems:
        raise ReportValidationError("；".join(problems))
    return urls


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", text.strip(), flags=re.UNICODE).strip("-")
    return s[:40] or "report"


def write_report(
    *,
    reports_dir: Path,
    report_type: str,
    market: str,
    title: str,
    content: str,
    product_name: str,
    min_sources: int,
    run_id: str = "",
    now: datetime | None = None,
) -> Path:
    """驗證並寫入報告檔，回傳路徑。"""
    if report_type not in REPORT_TYPES:
        raise ReportValidationError(f"report_type 必須是 {REPORT_TYPES} 之一")
    urls = validate_report(content, min_sources)
    now = now or datetime.now()
    market = market.strip().upper() or "EU"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{now:%Y%m%d-%H%M%S}_{report_type}_{market}_{_slug(title)}.md"
    header = (
        f"# {title}\n\n"
        f"> 產品：{product_name}｜市場：{market}｜類型：{report_type}｜"
        f"產生時間：{now:%Y-%m-%d %H:%M}｜來源數：{len(urls)}｜執行編號：{run_id or '-'}\n>\n"
        f"> 本報告由 AI Agent 自動產生，數據與法規內容請於決策前人工複核。\n\n"
    )
    body = re.sub(r"^#\s+.*\n+", "", content.lstrip(), count=1)  # 避免重複的一級標題
    path.write_text(header + body.rstrip() + "\n", encoding="utf-8")
    return path


@tool(
    "save_report",
    "把完成的 Markdown 報告存檔到 reports/ 資料夾。內容必須在內文附上來源連結，"
    "並有「## 資料來源」章節；不符合會被退回並說明原因。成功時回傳檔案路徑。",
    {
        "type": "object",
        "properties": {
            "report_type": {"type": "string", "enum": list(REPORT_TYPES)},
            "market": {"type": "string", "description": "ISO 國碼，例如 CZ"},
            "title": {"type": "string"},
            "content_markdown": {"type": "string", "description": "完整報告 Markdown"},
        },
        "required": ["report_type", "market", "title", "content_markdown"],
    },
)
async def save_report(args: dict[str, Any]) -> dict[str, Any]:
    ctx = get_context()
    try:
        path = write_report(
            reports_dir=ctx.settings.reports_dir,
            report_type=args["report_type"],
            market=args["market"],
            title=args["title"],
            content=args["content_markdown"],
            product_name=ctx.profile.product_name if ctx.profile else "-",
            min_sources=ctx.settings.min_report_sources,
            run_id=ctx.run_id,
        )
    except ReportValidationError as exc:
        log_action("report_rejected", reason=str(exc), run_id=ctx.run_id)
        return text_result(f"報告未通過檢查，請補強後重新呼叫 save_report：{exc}", is_error=True)
    rel = path.relative_to(ctx.settings.project_root)
    log_action("report_saved", path=str(rel), run_id=ctx.run_id)
    return text_result(f"報告已存檔：{rel}")
