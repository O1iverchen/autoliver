from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse


def validate_image_urls(image_urls: list[str]) -> list[str]:
    errors: list[str] = []
    cleaned = [url.strip() for url in image_urls if url and url.strip()]
    if not 1 <= len(cleaned) <= 6:
        errors.append("主图数量必须是 1 到 6 张。")
    for index, url in enumerate(cleaned, start=1):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"第 {index} 张图片不是有效的 http/https 直链。")
    return errors


def validate_price(value: str, field_name: str = "价格") -> list[str]:
    try:
        price = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return [f"{field_name}必须是正数字字符串。"]
    if price <= 0:
        return [f"{field_name}必须大于 0。"]
    return []


def validate_package_dimensions(length: int | float, width: int | float, height: int | float) -> list[str]:
    errors: list[str] = []
    for name, value in (("长度", length), ("宽度", width), ("高度", height)):
        if value < 1 or value > 700:
            errors.append(f"包裹{name}必须在 1 到 700 cm 之间。")
    return errors


def validate_weight(weight: str | int | float) -> list[str]:
    try:
        value = Decimal(str(weight).strip())
    except (InvalidOperation, AttributeError):
        return ["重量必须是数字，单位 kg。"]
    if value < Decimal("0.01") or value > Decimal("700"):
        return ["重量必须在 0.01 到 700 kg 之间。"]
    return []


def validate_required_fields(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = {
        "ru_title": "俄语标题不能为空。",
        "ru_web_description": "网站端详情不能为空。",
        "ru_mobile_description": "移动端详情不能为空。",
        "sku_code": "SKU code 不能为空。",
    }
    for key, message in required_fields.items():
        if not str(data.get(key, "")).strip():
            errors.append(message)

    if int(data.get("aliexpress_category_id") or 0) <= 0:
        errors.append("aliexpress_category_id 必须为正整数。")
    if int(data.get("freight_template_id") or 0) <= 0:
        errors.append("freight_template_id 必须为正整数。")
    if int(data.get("inventory") or 0) < 0:
        errors.append("库存不能小于 0。")
    return errors
