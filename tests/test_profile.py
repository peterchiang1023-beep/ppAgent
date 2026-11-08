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


# ---------- 多產品設定檔 ----------
from tests.conftest import EXAMPLE_PROFILE  # noqa: E402
from sales_agent.profiles.loader import list_products  # noqa: E402

MULTI = """
defaults:
  moq: 500
  target_markets: [{country: CZ, languages: [cs], currency: CZK, vat_rate: 0.21}]
  banned_words: [eco-friendly]
  certifications: [GPSR]
  min_profit_margin: 0.25
products:
  a:
    product_name: A
    cost: {unit_cost: 1}
    suggested_retail_price: {CZK: 100}
    banned_words: [rehab, eco-friendly]
    certifications: [PAH]
  b:
    product_name: B
    moq: 50
    cost: {unit_cost: 2}
    suggested_retail_price: {CZK: 200}
"""


def test_example_has_multiple_products():
    products = list_products(EXAMPLE_PROFILE)
    assert {"yoga-mat", "push-up-bar", "foam-roller"} <= set(products)
    for pid in products:
        p = load_profile(EXAMPLE_PROFILE, pid)
        assert p.market("CZ") and "eco-friendly" in p.banned_words


def test_multi_product_merge(tmp_path):
    f = tmp_path / "multi.yaml"
    f.write_text(MULTI, encoding="utf-8")
    a = load_profile(f, "a")
    assert a.moq == 500  # 來自 defaults
    assert a.banned_words == ["eco-friendly", "rehab"]  # 合併且去重
    assert a.certifications == ["GPSR", "PAH"]
    b = load_profile(f, "b")
    assert b.moq == 50  # 產品覆蓋 defaults
    assert b.banned_words == ["eco-friendly"]


def test_multi_product_requires_valid_product(tmp_path):
    f = tmp_path / "multi.yaml"
    f.write_text(MULTI, encoding="utf-8")
    with pytest.raises(ProfileError, match="請指定"):
        load_profile(f)
    with pytest.raises(ProfileError, match="沒有產品"):
        load_profile(f, "zzz")


def test_single_product_file_still_works(tmp_path):
    f = tmp_path / "single.yaml"
    f.write_text(
        "product_name: S\nmoq: 1\ncost: {unit_cost: 1}\nsuggested_retail_price: {EUR: 10}\n"
        "target_markets: [{country: DE, languages: [de], vat_rate: 0.19}]\nmin_profit_margin: 0.2\n",
        encoding="utf-8",
    )
    assert load_profile(f).product_name == "S"
    assert list_products(f) == {}
    with pytest.raises(ProfileError, match="單一產品"):
        load_profile(f, "x")
