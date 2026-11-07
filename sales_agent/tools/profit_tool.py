"""工具：單件利潤估算（含 VAT、關稅、平台佣金、物流、廣告與退貨成本）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from claude_agent_sdk import tool

from .context import get_context, text_result


@dataclass
class ProfitBreakdown:
    currency: str
    retail_price_gross: float
    vat_amount: float
    net_revenue: float           # 未稅售價
    landed_cost: float           # 到岸成本（出廠＋包材＋頭程＋關稅）
    platform_fee: float
    fulfillment_fee: float
    marketing_cost: float
    returns_cost: float
    total_cost: float
    net_profit: float
    net_margin: float            # 淨利 / 未稅售價
    min_profit_margin: float
    meets_floor: bool
    break_even_price_gross: float  # 達到利潤底線所需的含稅售價


def calculate_profit(
    *,
    retail_price_gross: float,
    vat_rate: float,
    unit_cost: float,
    packaging_cost: float = 0.0,
    shipping_per_unit: float = 0.0,
    duty_rate: float = 0.0,
    fx_rate: float = 1.0,
    platform_fee_rate: float = 0.0,
    fulfillment_fee: float = 0.0,
    marketing_rate: float = 0.0,
    return_rate: float = 0.0,
    min_profit_margin: float = 0.0,
    currency: str = "EUR",
) -> ProfitBreakdown:
    """純函式計算利潤。

    - 成本類（unit_cost、packaging_cost、shipping_per_unit）以成本幣別計，乘上 fx_rate 換成售價幣別。
    - 關稅以（出廠價＋頭程）為完稅價格估算（近似 CIF）。
    - platform_fee_rate 以含稅售價計（Amazon 等平台的慣例）。
    - marketing_rate 以未稅售價計；returns_cost = 未稅售價 × return_rate（保守估計：退貨品無法再售）。
    """
    if retail_price_gross <= 0:
        raise ValueError("retail_price_gross 必須大於 0")
    if fx_rate <= 0:
        raise ValueError("fx_rate 必須大於 0")
    for name, rate in {
        "vat_rate": vat_rate, "duty_rate": duty_rate, "platform_fee_rate": platform_fee_rate,
        "marketing_rate": marketing_rate, "return_rate": return_rate, "min_profit_margin": min_profit_margin,
    }.items():
        if not 0 <= rate < 1:
            raise ValueError(f"{name} 必須介於 0 與 1 之間")

    net_revenue = retail_price_gross / (1 + vat_rate)
    vat_amount = retail_price_gross - net_revenue

    customs_value = (unit_cost + shipping_per_unit) * fx_rate
    duty = customs_value * duty_rate
    landed_cost = (unit_cost + packaging_cost + shipping_per_unit) * fx_rate + duty

    platform_fee = retail_price_gross * platform_fee_rate
    marketing_cost = net_revenue * marketing_rate
    returns_cost = net_revenue * return_rate
    total_cost = landed_cost + platform_fee + fulfillment_fee + marketing_cost + returns_cost
    net_profit = net_revenue - total_cost
    net_margin = net_profit / net_revenue

    # 反推達到利潤底線的含稅售價：
    # net = P/(1+v)；成本 = fixed + P*pf + net*(mk+rt)；要求 net - 成本 >= m*net
    fixed = landed_cost + fulfillment_fee
    k = 1 - marketing_rate - return_rate - min_profit_margin - platform_fee_rate * (1 + vat_rate)
    break_even_net = fixed / k if k > 0 else float("inf")
    break_even_gross = break_even_net * (1 + vat_rate)

    r = lambda x: round(x, 2)  # noqa: E731
    return ProfitBreakdown(
        currency=currency,
        retail_price_gross=r(retail_price_gross),
        vat_amount=r(vat_amount),
        net_revenue=r(net_revenue),
        landed_cost=r(landed_cost),
        platform_fee=r(platform_fee),
        fulfillment_fee=r(fulfillment_fee),
        marketing_cost=r(marketing_cost),
        returns_cost=r(returns_cost),
        total_cost=r(total_cost),
        net_profit=r(net_profit),
        net_margin=round(net_margin, 4),
        min_profit_margin=min_profit_margin,
        meets_floor=net_margin >= min_profit_margin,
        break_even_price_gross=r(break_even_gross),
    )


@tool(
    "estimate_profit",
    "用產品設定檔的成本，估算在某國某通路以指定含稅售價銷售時的單件淨利與是否達到利潤底線。"
    "fx_rate 為 1 單位成本幣別（通常 USD）可換得多少售價幣別，請先查證最新匯率。",
    {
        "type": "object",
        "properties": {
            "market": {"type": "string", "description": "ISO 國碼，用來取得 VAT 稅率"},
            "retail_price_gross": {"type": "number", "description": "含 VAT 售價（售價幣別）"},
            "currency": {"type": "string", "description": "售價幣別，例如 EUR、CZK"},
            "fx_rate": {"type": "number", "description": "1 成本幣別 = ? 售價幣別"},
            "platform_fee_rate": {"type": "number", "description": "平台佣金率 0~1（以含稅價計）"},
            "fulfillment_fee": {"type": "number", "description": "每件物流／FBA 費（售價幣別）"},
            "marketing_rate": {"type": "number", "description": "廣告費占未稅售價比例 0~1"},
            "return_rate": {"type": "number", "description": "退貨率 0~1"},
            "vat_rate": {"type": "number", "description": "選填：覆寫設定檔中的 VAT 稅率"},
        },
        "required": ["market", "retail_price_gross", "currency", "fx_rate"],
    },
    annotations={"readOnlyHint": True},
)
async def estimate_profit(args: dict[str, Any]) -> dict[str, Any]:
    profile = get_context().profile
    if profile is None:
        return text_result("尚未載入產品設定檔", is_error=True)
    m = profile.market(args["market"])
    vat_rate = args.get("vat_rate")
    if vat_rate is None:
        if m is None:
            return text_result(f"設定檔中沒有 {args['market']} 的 VAT 稅率，請傳入 vat_rate", is_error=True)
        vat_rate = m.vat_rate
    try:
        result = calculate_profit(
            retail_price_gross=float(args["retail_price_gross"]),
            vat_rate=float(vat_rate),
            unit_cost=profile.cost.unit_cost,
            packaging_cost=profile.cost.packaging_cost,
            shipping_per_unit=profile.cost.shipping_to_eu_per_unit,
            duty_rate=profile.cost.duty_rate,
            fx_rate=float(args["fx_rate"]),
            platform_fee_rate=float(args.get("platform_fee_rate", 0)),
            fulfillment_fee=float(args.get("fulfillment_fee", 0)),
            marketing_rate=float(args.get("marketing_rate", 0)),
            return_rate=float(args.get("return_rate", 0)),
            min_profit_margin=profile.min_profit_margin,
            currency=args["currency"],
        )
    except (ValueError, TypeError) as exc:
        return text_result(f"參數錯誤：{exc}", is_error=True)
    return text_result(json.dumps(asdict(result), ensure_ascii=False, indent=2))
