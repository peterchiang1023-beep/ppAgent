import pytest

from sales_agent.agents import all_specs
from sales_agent.core.safety import evaluate_tool_call
from sales_agent.tools.draft_tool import DraftQueue, create_draft
from sales_agent.tools.email_tool import NotConfiguredEmailProvider, OutreachEmail
from sales_agent.tools.marketplace_tool import AmazonSPAPIClient, ListingContent
from tests.conftest import result_text


def test_draft_lifecycle(tmp_path):
    q = DraftQueue(tmp_path)
    d = q.create("email", "email", "開發信給 ABC", {"body": "hi"})
    assert q.get(d.id).status == "pending"
    assert [x.id for x in q.list("pending")] == [d.id]
    q.set_status(d.id, "approved", "ok")
    assert q.get(d.id).status == "approved"
    with pytest.raises(ValueError):
        q.set_status(d.id, "rejected")  # 不可重複審核
    with pytest.raises(ValueError):
        q.create("launch_rocket", "x", "y", {})
    with pytest.raises(ValueError):
        q.get("../../etc/passwd")


async def test_create_draft_tool(tool_ctx):
    res = await create_draft.handler(
        {"action_type": "listing", "channel": "amazon_de", "summary": "上架草稿", "payload": {"title": "x"}}
    )
    assert "pending" in result_text(res)
    assert len(DraftQueue(tool_ctx.settings.drafts_dir).list()) == 1


def test_stub_clients_never_call_external_apis():
    with pytest.raises(NotImplementedError):
        NotConfiguredEmailProvider().send(OutreachEmail("ABC", "Buyer", "cs", "s", "b"))
    with pytest.raises(NotImplementedError):
        AmazonSPAPIClient().submit_listing(ListingContent("amazon_de", "de", "t", [], "d"))


def test_agent_specs(settings):
    specs = {s.name: s for s in all_specs(settings)}
    assert set(specs) == {"research", "market_compliance", "lead_gen", "listing", "social", "analytics"}
    assert specs["research"].implemented and specs["market_compliance"].implemented
    assert not any(specs[n].implemented for n in ("lead_gen", "listing", "social", "analytics"))
    for s in specs.values():
        # 子 Agent 宣告的工具都必須通過安全白名單
        for t in s.tools:
            assert evaluate_tool_call(t, {}).allowed, t
    assert "WebSearch" in specs["research"].tools


def test_supervisor_options(settings, profile, tmp_path):
    from sales_agent.core.budget import BudgetTracker
    from sales_agent.core.supervisor import Supervisor

    sup = Supervisor(settings, profile, BudgetTracker(tmp_path, 5, 100))
    opts = sup.build_options()
    assert set(opts.agents) == {"research", "market_compliance"}
    assert "Bash" in opts.disallowed_tools
    assert opts.max_budget_usd == settings.run_budget_usd
    assert "草稿" in opts.system_prompt


async def test_pre_tool_hook_blocks_and_counts(settings, profile, tmp_path):
    from sales_agent.core.budget import BudgetTracker
    from sales_agent.core.supervisor import Supervisor

    budget = BudgetTracker(tmp_path, 5, 1)
    sup = Supervisor(settings, profile, budget)
    denied = await sup._pre_tool_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}, "t1", None)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert await sup._pre_tool_hook({"tool_name": "WebSearch", "tool_input": {"query": "x"}}, "t2", None) == {}
    stopped = await sup._pre_tool_hook({"tool_name": "WebSearch", "tool_input": {"query": "y"}}, "t3", None)
    assert stopped["continue_"] is False
