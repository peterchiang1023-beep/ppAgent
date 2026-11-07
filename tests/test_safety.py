import pytest

from sales_agent.core.safety import evaluate_tool_call, is_blocked_url, redact_obj, redact_pii


@pytest.mark.parametrize("tool", ["WebSearch", "Agent", "Task", "mcp__sales__save_report"])
def test_allowed(tool):
    assert evaluate_tool_call(tool, {}).allowed


@pytest.mark.parametrize("tool", ["Bash", "Write", "Edit", "mcp__claude-in-chrome__click",
                                  "mcp__sales__unknown_tool", "SomethingNew"])
def test_denied_by_default(tool):
    assert not evaluate_tool_call(tool, {}).allowed


@pytest.mark.parametrize("tool", ["mcp__sales__send_email", "mcp__sales__publish_listing",
                                  "mcp__sales__update_price", "mcp__sales__make_payment"])
def test_external_actions_require_draft(tool):
    d = evaluate_tool_call(tool, {})
    assert not d.allowed and "草稿模式" in d.reason


def test_draft_action_type_validated():
    assert evaluate_tool_call("mcp__sales__create_draft", {"action_type": "email"}).allowed
    assert not evaluate_tool_call("mcp__sales__create_draft", {"action_type": "delete_all"}).allowed


@pytest.mark.parametrize("url", [
    "https://sellercentral.amazon.de/inventory",
    "https://sellercentral-europe.amazon.com/home",
    "https://seller.tiktok.com/",
    "https://admin.shopify.com/store/x",
    "file:///etc/passwd",
])
def test_blocked_urls(url):
    assert is_blocked_url(url)
    assert not evaluate_tool_call("WebFetch", {"url": url}).allowed


@pytest.mark.parametrize("url", ["https://www.amazon.de/dp/B0TEST", "https://eur-lex.europa.eu/eli/reg/2023/988/oj",
                                 "https://www.alza.cz/"])
def test_public_urls_allowed(url):
    assert not is_blocked_url(url)
    assert evaluate_tool_call("WebFetch", {"url": url}).allowed


def test_redact_pii():
    text = "聯絡 jan.novak@firma.cz 或 +420 777 123 456，網址 https://firma.cz/2024/10/01"
    out = redact_pii(text)
    assert "jan.novak" not in out and "777" not in out
    assert "[EMAIL]" in out and "[PHONE]" in out
    assert "https://firma.cz/2024/10/01" in out
    assert redact_obj({"a": ["x@y.com"]}) == {"a": ["[EMAIL]"]}
