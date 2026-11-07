"""每日 API 呼叫次數與預算追蹤。

用量存在 logs/usage_YYYYMMDD.json，跨次執行累計；超過上限就停止並通知。
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from sales_agent.logging_setup import get_logger, log_action

logger = get_logger("budget")


class BudgetExceeded(RuntimeError):
    """超過每日預算或呼叫次數上限。"""


@dataclass
class DailyUsage:
    day: str
    cost_usd: float = 0.0
    tool_calls: int = 0
    runs: int = 0
    tool_call_breakdown: dict[str, int] = field(default_factory=dict)


class BudgetTracker:
    """每日用量追蹤器（執行緒安全，資料持久化到檔案）。"""

    def __init__(
        self,
        logs_dir: Path,
        daily_budget_usd: float,
        daily_tool_call_limit: int,
        today: date | None = None,
    ) -> None:
        self.logs_dir = logs_dir
        self.daily_budget_usd = daily_budget_usd
        self.daily_tool_call_limit = daily_tool_call_limit
        self._today = today
        self._lock = threading.Lock()
        self.usage = self._load()

    # ---- 持久化 ----
    @property
    def day(self) -> date:
        return self._today or date.today()

    @property
    def path(self) -> Path:
        return self.logs_dir / f"usage_{self.day:%Y%m%d}.json"

    def _load(self) -> DailyUsage:
        if self.path.is_file():
            try:
                return DailyUsage(**json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("用量檔損毀，重新計算：%s", exc)
        return DailyUsage(day=self.day.isoformat())

    def _save(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(self.usage), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- 查詢 ----
    @property
    def remaining_budget_usd(self) -> float:
        return max(0.0, self.daily_budget_usd - self.usage.cost_usd)

    @property
    def remaining_tool_calls(self) -> int:
        return max(0, self.daily_tool_call_limit - self.usage.tool_calls)

    def run_budget(self, run_cap_usd: float) -> float:
        """本次執行可用預算 = min(單次上限, 今日剩餘)。"""
        return round(min(run_cap_usd, self.remaining_budget_usd), 4)

    def status(self) -> dict:
        return {
            "day": self.usage.day,
            "cost_usd": round(self.usage.cost_usd, 4),
            "daily_budget_usd": self.daily_budget_usd,
            "remaining_budget_usd": round(self.remaining_budget_usd, 4),
            "tool_calls": self.usage.tool_calls,
            "daily_tool_call_limit": self.daily_tool_call_limit,
            "remaining_tool_calls": self.remaining_tool_calls,
            "runs": self.usage.runs,
        }

    # ---- 更新 ----
    def check_can_start(self, min_budget_usd: float = 0.05) -> None:
        """開始執行前檢查；不足則丟出 BudgetExceeded。"""
        if self.remaining_budget_usd < min_budget_usd:
            self._notify("daily_budget", f"今日預算已用盡（{self.usage.cost_usd:.2f}/{self.daily_budget_usd} USD）")
        if self.remaining_tool_calls <= 0:
            self._notify("daily_tool_calls", f"今日工具呼叫已達上限（{self.daily_tool_call_limit} 次）")

    def start_run(self) -> None:
        with self._lock:
            self.usage.runs += 1
            self._save()

    def register_tool_call(self, tool_name: str) -> bool:
        """登記一次工具呼叫。回傳 False 表示已超過上限、應停止。"""
        with self._lock:
            if self.usage.tool_calls >= self.daily_tool_call_limit:
                return False
            self.usage.tool_calls += 1
            self.usage.tool_call_breakdown[tool_name] = (
                self.usage.tool_call_breakdown.get(tool_name, 0) + 1
            )
            self._save()
            return True

    def add_cost(self, usd: float | None) -> None:
        if not usd:
            return
        with self._lock:
            self.usage.cost_usd += float(usd)
            self._save()
        if self.usage.cost_usd >= self.daily_budget_usd:
            log_action("budget_alert", kind="daily_budget", status=self.status())
            logger.warning("今日預算已達上限：%s", self.status())

    def _notify(self, kind: str, message: str) -> None:
        """通知（第一階段：日誌＋例外，由 CLI 以紅字顯示）。"""
        log_action("budget_alert", kind=kind, message=message, status=self.status())
        logger.error(message)
        raise BudgetExceeded(message)
