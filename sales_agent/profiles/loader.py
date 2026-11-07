"""客製化層：讀取並驗證 profiles/*.yaml 產品與市場設定。

換產品只需要換一個 YAML 檔，程式碼不需修改。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileError(ValueError):
    """設定檔格式錯誤。"""


class Cost(BaseModel):
    """成本結構（單位：currency 欄位指定的幣別，每件）。"""

    currency: str = "USD"
    unit_cost: float = Field(..., ge=0, description="工廠出廠單價（FOB）")
    packaging_cost: float = Field(0, ge=0, description="包材成本")
    shipping_to_eu_per_unit: float = Field(0, ge=0, description="中國到歐洲倉的每件頭程運費")
    duty_rate: float = Field(0, ge=0, le=1, description="進口關稅稅率（0~1）")


class TargetMarket(BaseModel):
    """目標國家與語言。"""

    country: str = Field(..., description="ISO 3166-1 alpha-2 國碼，例如 CZ、DE")
    languages: list[str] = Field(..., min_length=1, description="ISO 639-1 語言碼")
    currency: str = "EUR"
    vat_rate: float = Field(..., ge=0, le=1, description="標準增值稅率（0~1）")

    @field_validator("country")
    @classmethod
    def _upper_country(cls, v: str) -> str:
        return v.strip().upper()


class ProductProfile(BaseModel):
    """產品設定檔。"""

    product_name: str
    category: str = ""
    description: str = ""
    specs: dict[str, Any] = Field(default_factory=dict, description="規格（自由欄位）")
    cost: Cost
    suggested_retail_price: dict[str, float] = Field(
        ..., description="各幣別建議售價（含稅），例如 {EUR: 24.9, CZK: 599}"
    )
    moq: int = Field(..., gt=0, description="最小訂購量")
    target_markets: list[TargetMarket] = Field(..., min_length=1)
    target_channels: list[str] = Field(default_factory=list, description="目標通路")
    brand_voice: str = ""
    banned_words: list[str] = Field(default_factory=list, description="文案禁用字詞")
    certifications: list[str] = Field(default_factory=list, description="已具備或需準備的認證文件")
    min_profit_margin: float = Field(..., ge=0, le=1, description="利潤底線（淨利率 0~1）")

    @model_validator(mode="after")
    def _unique_markets(self) -> "ProductProfile":
        codes = [m.country for m in self.target_markets]
        if len(codes) != len(set(codes)):
            raise ValueError("target_markets 中的國家重複")
        return self

    # ---- 便利方法 ----
    def market(self, country: str) -> TargetMarket | None:
        country = country.strip().upper()
        return next((m for m in self.target_markets if m.country == country), None)

    def find_banned_words(self, text: str) -> list[str]:
        """回傳文字中出現的禁用字詞（不分大小寫）。"""
        lower = text.lower()
        return [w for w in self.banned_words if w.lower() in lower]

    def to_prompt_context(self) -> str:
        """轉成給 Agent 閱讀的 YAML 文字。"""
        return yaml.safe_dump(self.model_dump(), allow_unicode=True, sort_keys=False)


def load_profile(path: str | Path) -> ProductProfile:
    """讀取 YAML 並驗證欄位。"""
    p = Path(path)
    if not p.is_file():
        raise ProfileError(f"找不到設定檔：{p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"YAML 格式錯誤：{exc}") from exc
    try:
        return ProductProfile.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError
        raise ProfileError(f"設定檔欄位驗證失敗（{p}）：\n{exc}") from exc
