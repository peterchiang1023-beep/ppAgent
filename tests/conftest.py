"""共用測試設定：所有輸出寫到 pytest 的暫存資料夾，不污染專案。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sales_agent.config import Settings
from sales_agent.core.budget import BudgetTracker
from sales_agent.logging_setup import setup_logging
from sales_agent.profiles.loader import load_profile
from sales_agent.tools.context import ToolContext, set_context

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PROFILE = ROOT / "profiles" / "example.yaml"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(
        anthropic_api_key="test-key",
        min_report_sources=3,
        project_root=tmp_path,
        reports_dir=tmp_path / "reports",
        drafts_dir=tmp_path / "drafts",
        logs_dir=tmp_path / "logs",
    )
    s.ensure_dirs()
    setup_logging(s.logs_dir)
    return s


@pytest.fixture
def profile():
    return load_profile(EXAMPLE_PROFILE, "yoga-mat")


@pytest.fixture
def tool_ctx(settings, profile):
    budget = BudgetTracker(settings.logs_dir, 5.0, 10)
    ctx = ToolContext(settings=settings, profile=profile, budget=budget, run_id="test-run")
    set_context(ctx)
    return ctx


def result_text(result: dict) -> str:
    return result["content"][0]["text"]
