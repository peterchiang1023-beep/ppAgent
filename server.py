"""通用銷售 AI Agent — HTTP API。

啟動（本機）：
    uv run uvicorn server:app --reload --port 8000
    # 互動式文件：http://127.0.0.1:8000/docs

一次研究可能要跑好幾分鐘，所以採「工作」模式：
    POST /runs          建立任務，立刻回傳 run_id（202）
    GET  /runs/{run_id} 查詢狀態與結果（status: running / succeeded / failed）

同一時間只允許一個任務執行：工具層用模組層級的 ToolContext 傳遞狀態，
並行執行會互相覆蓋，所以忙碌時回傳 409。

若設定環境變數 SERVER_API_KEY，所有請求都必須帶 `X-API-Key` 標頭。
"""

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from rich.console import Console

from sales_agent.config import ConfigError, load_settings
from sales_agent.core.budget import BudgetExceeded, BudgetTracker
from sales_agent.logging_setup import log_action, setup_logging
from sales_agent.profiles.loader import ProfileError, load_profile

settings = load_settings()
setup_logging(settings.logs_dir)
PROFILES_DIR = settings.project_root / "profiles"
console = Console()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("SERVER_API_KEY", "").strip()
    if expected and not (x_api_key and secrets.compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=401, detail="缺少或錯誤的 X-API-Key")


app = FastAPI(title="ppAgent API", version="0.1.0", dependencies=[Depends(require_api_key)])

# ---------- 執行狀態（存在記憶體，重啟後清空；報告與日誌仍在磁碟上） ----------
_runs: dict[str, dict] = {}
_run_lock = asyncio.Lock()
_background: set[asyncio.Task] = set()


class RunRequest(BaseModel):
    task: Literal["research", "compliance"]
    market: str = Field(min_length=2, max_length=3, description="ISO 國碼，例如 CZ、DE")
    profile: str = Field(default="example", description="profiles/ 底下的設定檔名稱（不含 .yaml）")


class DraftDecision(BaseModel):
    note: str = ""


def _profile_path(name: str) -> Path:
    path = (PROFILES_DIR / f"{name}.yaml").resolve()
    if path.parent != PROFILES_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"找不到設定檔：{name}")
    return path


def _budget() -> BudgetTracker:
    return BudgetTracker(settings.logs_dir, settings.daily_budget_usd, settings.daily_tool_call_limit)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- 端點 ----------
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "busy": _run_lock.locked()}


@app.post("/runs", status_code=202)
async def create_run(req: RunRequest) -> dict:
    from sales_agent.core.supervisor import Supervisor
    from sales_agent.core.tasks import TASKS

    try:
        settings.require_api_key()
        profile = load_profile(_profile_path(req.profile))
    except (ConfigError, ProfileError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="已有任務執行中，請稍後再試")
    await _run_lock.acquire()  # 在同一個事件迴圈中，檢查與取得之間不會被搶走

    try:
        market = req.market.strip().upper()
        budget = _budget()
        budget.check_can_start()
        supervisor = Supervisor(settings, profile, budget, console)
    except BudgetExceeded as exc:
        _run_lock.release()
        raise HTTPException(status_code=429, detail=f"預算上限：{exc}") from exc
    except Exception:
        _run_lock.release()
        raise

    run_id = supervisor.run_id
    task_name = f"{req.task}:{market}"
    _runs[run_id] = {"run_id": run_id, "task": task_name, "profile": req.profile,
                     "status": "running", "created_at": _now()}
    log_action("api_run_create", run_id=run_id, task=task_name, profile=req.profile)

    async def _execute() -> None:
        try:
            result = await supervisor.run(TASKS[req.task](profile, market), task_name=task_name)
            ok = result.success and bool(result.reports)
            _runs[run_id].update(status="succeeded" if ok else "failed", result=asdict(result))
        except BudgetExceeded as exc:
            _runs[run_id].update(status="failed", error=f"預算上限：{exc}")
        except Exception as exc:  # supervisor 已寫入日誌
            _runs[run_id].update(status="failed", error=repr(exc))
        finally:
            _runs[run_id]["finished_at"] = _now()
            _run_lock.release()

    task = asyncio.create_task(_execute())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return _runs[run_id]


@app.get("/runs")
async def list_runs() -> list[dict]:
    return sorted(_runs.values(), key=lambda r: r["created_at"], reverse=True)


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="找不到此執行編號（伺服器重啟後會清空）")
    return _runs[run_id]


@app.get("/reports")
async def list_reports() -> list[str]:
    return sorted((p.name for p in settings.reports_dir.glob("*.md")), reverse=True)


@app.get("/reports/{filename}", response_class=PlainTextResponse)
async def get_report(filename: str) -> str:
    path = (settings.reports_dir / filename).resolve()
    if path.parent != settings.reports_dir.resolve() or path.suffix != ".md" or not path.is_file():
        raise HTTPException(status_code=404, detail="找不到報告")
    return path.read_text(encoding="utf-8")


@app.get("/budget")
async def budget_status() -> dict:
    return _budget().status()


@app.get("/drafts")
async def list_drafts(status: Literal["pending", "approved", "rejected"] | None = None) -> list[dict]:
    from sales_agent.tools.draft_tool import DraftQueue

    return [d.__dict__ for d in DraftQueue(settings.drafts_dir).list(status)]


@app.get("/drafts/{draft_id}")
async def get_draft(draft_id: str) -> dict:
    from sales_agent.tools.draft_tool import DraftQueue

    try:
        return DraftQueue(settings.drafts_dir).get(draft_id).__dict__
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/drafts/{draft_id}/{decision}")
async def decide_draft(draft_id: str, decision: Literal["approve", "reject"], body: DraftDecision) -> dict:
    from sales_agent.tools.draft_tool import DraftQueue

    status = "approved" if decision == "approve" else "rejected"
    try:
        d = DraftQueue(settings.drafts_dir).set_status(draft_id, status, body.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_action("api_draft_decision", draft_id=draft_id, status=status)
    return d.__dict__
