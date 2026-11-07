from datetime import datetime

import pytest

from sales_agent.tools.report_tool import (
    ReportValidationError,
    extract_urls,
    save_report,
    validate_report,
    write_report,
)
from tests.conftest import result_text

GOOD = """# 測試報告

市場成長 5% [Eurostat](https://ec.europa.eu/eurostat/data)。
競品售價 499 CZK [Alza](https://www.alza.cz/item1)，另見 https://www.heureka.cz/x.

## 資料來源
- https://ec.europa.eu/eurostat/data
- https://www.alza.cz/item1
- https://www.heureka.cz/x
"""


def test_extract_urls_dedup():
    urls = extract_urls(GOOD)
    assert urls == ["https://ec.europa.eu/eurostat/data", "https://www.alza.cz/item1", "https://www.heureka.cz/x"]


def test_validate_requires_sources_and_section():
    assert len(validate_report(GOOD, 3)) == 3
    with pytest.raises(ReportValidationError, match="至少需要"):
        validate_report(GOOD, 10)
    with pytest.raises(ReportValidationError, match="資料來源"):
        validate_report(GOOD.replace("## 資料來源", "## 結語"), 1)


def test_write_report(tmp_path):
    path = write_report(
        reports_dir=tmp_path, report_type="research", market="cz", title="收納盒 捷克 研究",
        content=GOOD, product_name="收納盒", min_sources=3, now=datetime(2026, 1, 2, 3, 4, 5),
    )
    assert path.name.startswith("20260102-030405_research_CZ_")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 收納盒 捷克 研究")
    assert text.count("# 測試報告") == 0  # 原本的一級標題被移除
    assert "來源數：3" in text


def test_write_report_rejects_type(tmp_path):
    with pytest.raises(ReportValidationError):
        write_report(reports_dir=tmp_path, report_type="hack", market="CZ", title="t",
                     content=GOOD, product_name="p", min_sources=1)


async def test_save_report_tool(tool_ctx):
    ok = await save_report.handler(
        {"report_type": "research", "market": "CZ", "title": "T", "content_markdown": GOOD}
    )
    assert "報告已存檔：reports/" in result_text(ok)
    assert len(list(tool_ctx.settings.reports_dir.glob("*.md"))) == 1

    bad = await save_report.handler(
        {"report_type": "research", "market": "CZ", "title": "T", "content_markdown": "沒有來源"}
    )
    assert bad.get("is_error")
    assert len(list(tool_ctx.settings.reports_dir.glob("*.md"))) == 1
