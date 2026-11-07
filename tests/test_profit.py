import json

import pytest

from sales_agent.tools.profit_tool import calculate_profit, estimate_profit
from tests.conftest import result_text


def test_simple_profit_no_fees():
    r = calculate_profit(retail_price_gross=121, vat_rate=0.21, unit_cost=50)
    assert r.net_revenue == 100
    assert r.vat_amount == 21
    assert r.net_profit == 50
    assert r.net_margin == 0.5


def test_full_cost_breakdown():
    r = calculate_profit(
        retail_price_gross=119, vat_rate=0.19, unit_cost=10, packaging_cost=1,
        shipping_per_unit=2, duty_rate=0.1, fx_rate=1.0, platform_fee_rate=0.15,
        fulfillment_fee=5, marketing_rate=0.1, return_rate=0.05, min_profit_margin=0.25,
    )
    # 到岸成本 = 13 + 關稅 (10+2)*0.1 = 14.2
    assert r.landed_cost == 14.2
    assert r.platform_fee == 17.85
    assert r.total_cost == pytest.approx(14.2 + 17.85 + 5 + 10 + 5, abs=0.01)
    assert r.meets_floor is True


def test_break_even_price_hits_floor_exactly():
    kwargs = dict(vat_rate=0.21, unit_cost=8, shipping_per_unit=1, duty_rate=0.05, fx_rate=0.92,
                  platform_fee_rate=0.15, fulfillment_fee=3.5, marketing_rate=0.1,
                  return_rate=0.03, min_profit_margin=0.25)
    low = calculate_profit(retail_price_gross=15, **kwargs)
    assert low.meets_floor is False
    at_floor = calculate_profit(retail_price_gross=low.break_even_price_gross, **kwargs)
    assert at_floor.net_margin == pytest.approx(0.25, abs=0.002)


@pytest.mark.parametrize("bad", [{"retail_price_gross": 0}, {"fx_rate": 0}, {"vat_rate": 1.5}])
def test_invalid_inputs(bad):
    kwargs = dict(retail_price_gross=10, vat_rate=0.2, unit_cost=1, fx_rate=1.0) | bad
    with pytest.raises(ValueError):
        calculate_profit(**kwargs)


async def test_estimate_profit_tool_uses_profile(tool_ctx):
    res = await estimate_profit.handler(
        {"market": "CZ", "retail_price_gross": 499, "currency": "CZK", "fx_rate": 23.0,
         "platform_fee_rate": 0.12, "fulfillment_fee": 60}
    )
    data = json.loads(result_text(res))
    assert data["currency"] == "CZK"
    assert data["min_profit_margin"] == 0.25
    assert data["vat_amount"] == pytest.approx(499 - 499 / 1.21, abs=0.01)


async def test_estimate_profit_unknown_market_requires_vat(tool_ctx):
    res = await estimate_profit.handler(
        {"market": "FR", "retail_price_gross": 20, "currency": "EUR", "fx_rate": 0.9}
    )
    assert res.get("is_error")
