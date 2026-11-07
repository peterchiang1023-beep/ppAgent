from datetime import date

import pytest

from sales_agent.core.budget import BudgetExceeded, BudgetTracker


def test_tool_call_limit(tmp_path):
    b = BudgetTracker(tmp_path, daily_budget_usd=5, daily_tool_call_limit=2)
    assert b.register_tool_call("WebSearch")
    assert b.register_tool_call("WebSearch")
    assert not b.register_tool_call("WebSearch")
    assert b.usage.tool_call_breakdown == {"WebSearch": 2}
    with pytest.raises(BudgetExceeded):
        b.check_can_start()


def test_cost_persists_across_instances(tmp_path):
    d = date(2026, 11, 7)
    b = BudgetTracker(tmp_path, 5, 100, today=d)
    b.add_cost(1.25)
    b2 = BudgetTracker(tmp_path, 5, 100, today=d)
    assert b2.usage.cost_usd == 1.25
    assert b2.remaining_budget_usd == 3.75
    # 不同日期重新計算
    assert BudgetTracker(tmp_path, 5, 100, today=date(2026, 11, 8)).usage.cost_usd == 0


def test_run_budget_capped_by_remaining(tmp_path):
    b = BudgetTracker(tmp_path, 5, 100)
    assert b.run_budget(2) == 2
    b.add_cost(4.5)
    assert b.run_budget(2) == 0.5
    b.add_cost(0.5)
    with pytest.raises(BudgetExceeded):
        b.check_can_start()


async def test_budget_tool(tool_ctx):
    import json

    from sales_agent.tools.budget_tool import get_budget_status
    from tests.conftest import result_text

    data = json.loads(result_text(await get_budget_status.handler({})))
    assert data["daily_tool_call_limit"] == 10
