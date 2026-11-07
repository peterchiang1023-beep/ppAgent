"""全域設定：一律從 .env / 環境變數讀取，程式碼中不寫死任何金鑰。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄（main.py 所在位置）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """設定錯誤（例如缺少 API 金鑰）。"""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError as exc:
        raise ConfigError(f"環境變數 {name} 必須是數字，目前為：{raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


@dataclass
class Settings:
    """執行期設定。"""

    anthropic_api_key: str = ""
    supervisor_model: str = "claude-opus-5-5"
    subagent_model: str = "claude-sonnet-5-5"
    daily_budget_usd: float = 5.0
    daily_tool_call_limit: int = 300
    run_budget_usd: float = 2.0
    max_turns: int = 60
    min_report_sources: int = 5

    project_root: Path = PROJECT_ROOT
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    drafts_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "drafts")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")

    def ensure_dirs(self) -> None:
        for d in (self.reports_dir, self.drafts_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def require_api_key(self) -> None:
        """呼叫 Claude 前檢查金鑰是否存在。"""
        if not self.anthropic_api_key:
            raise ConfigError(
                "找不到 ANTHROPIC_API_KEY。請複製 .env.example 為 .env 並填入金鑰。"
            )


def load_settings(env_file: Path | None = None) -> Settings:
    """讀取 .env 並建立 Settings。"""
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    settings = Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        supervisor_model=os.getenv("SUPERVISOR_MODEL", "").strip() or "claude-opus-5-5",
        subagent_model=os.getenv("SUBAGENT_MODEL", "").strip() or "claude-sonnet-5-5",
        daily_budget_usd=_env_float("DAILY_BUDGET_USD", 5.0),
        daily_tool_call_limit=_env_int("DAILY_TOOL_CALL_LIMIT", 300),
        run_budget_usd=_env_float("RUN_BUDGET_USD", 2.0),
        max_turns=_env_int("MAX_TURNS", 60),
        min_report_sources=_env_int("MIN_REPORT_SOURCES", 5),
    )
    settings.ensure_dirs()
    return settings
