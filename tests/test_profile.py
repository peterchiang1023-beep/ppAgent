import pytest

from sales_agent.profiles.loader import ProfileError, load_profile
from tests.conftest import result_text


def test_example_profile_loads(profile):
    assert profile.moq == 500
    assert profile.market("cz").vat_rate == 0.21
    assert profile.market("FR") is None
    assert 0 < profile.min_profit_margin < 1
    assert profile.certifications


def test_banned_words_case_insensitive(profile):
    assert "eco-friendly" in profile.find_banned_words("A very ECO-FRIENDLY box")
    assert profile.find_banned_words("A sturdy foldable box") == []


def test_missing_file(tmp_path):
    with pytest.raises(ProfileError):
        load_profile(tmp_path / "nope.yaml")


def test_invalid_profile(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("product_name: x\nmoq: 0\n", encoding="utf-8")
    with pytest.raises(ProfileError):
        load_profile(p)


async def test_profile_tool(tool_ctx):
    from sales_agent.tools.profile_tool import get_product_profile

    text = result_text(await get_product_profile.handler({"market": "DE"}))
    assert "product_name" in text and '"country": "DE"' in text
    text = result_text(await get_product_profile.handler({"market": "FR"}))
    assert "沒有 FR" in text
