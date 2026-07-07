from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlparse

import requests


@dataclass
class ProductPageInfo:
    ok: bool
    title: str = ""
    description: str = ""
    weight_kg: Optional[str] = None
    length_cm: Optional[int] = None
    width_cm: Optional[int] = None
    height_cm: Optional[int] = None
    error: str = ""


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    try:
        value = value.encode("utf-8").decode("unicode_escape")
    except UnicodeError:
        pass
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\\/", "/")
    value = value.replace('\\"', '"')
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _extract_jsonish_value(content: str, keys: tuple[str, ...]) -> str:
    for key in keys:
        patterns = [
            rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"',
            rf"'{re.escape(key)}'\s*:\s*'((?:\\.|[^'\\])*)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                value = match.group(1)
                try:
                    value = json.loads(f'"{value}"')
                except json.JSONDecodeError:
                    pass
                cleaned = _clean_text(value)
                if cleaned:
                    return cleaned
    return ""


def _extract_meta(content: str, name: str) -> str:
    patterns = [
        rf'<meta[^>]+name=["\\\']{re.escape(name)}["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
        rf'<meta[^>]+property=["\\\']{re.escape(name)}["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))
    return ""


def _extract_title(content: str) -> str:
    json_title = _extract_jsonish_value(
        content,
        (
            "subject",
            "title",
            "offerTitle",
            "productTitle",
            "productName",
            "name",
        ),
    )
    if json_title:
        return _normalize_title(json_title)
    for name in ("og:title", "title"):
        value = _extract_meta(content, name)
        if value:
            return _normalize_title(value)
    match = re.search(r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return _normalize_title(_clean_text(match.group(1)))
    return ""


def _normalize_title(title: str) -> str:
    title = re.sub(r"[-_—|].*?(1688|阿里巴巴).*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def _to_kg(value: str, unit: str) -> Optional[str]:
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    unit = unit.lower()
    if unit in {"g", "克"}:
        number = number / Decimal("1000")
    return str(number.normalize())


def _extract_weight(content: str) -> Optional[str]:
    compact = _clean_text(content)
    patterns = [
        r"(?:包装重量|毛重|重量|净重|商品重量|产品重量)[\"'：:\s]*([0-9]+(?:\.[0-9]+)?)\s*(kg|KG|千克|公斤|g|克)",
        r"(?:weight|grossWeight|packageWeight)[\"'：:\s]*([0-9]+(?:\.[0-9]+)?)\s*(kg|KG|千克|公斤|g|克)?",
        r"([0-9]+(?:\.[0-9]+)?)\s*(kg|KG|千克|公斤)\s*(?:/件|每件)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            unit = match.group(2) if len(match.groups()) >= 2 and match.group(2) else "kg"
            return _to_kg(match.group(1), unit)
    return None


def _extract_dimensions(content: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    compact = _clean_text(content)
    patterns = [
        r"(?:包装尺寸|尺寸|规格|商品尺寸|产品尺寸)[\"'：:\s]*([0-9]+)\s*[xX*×]\s*([0-9]+)\s*[xX*×]\s*([0-9]+)\s*(cm|厘米)?",
        r"长[：:\s]*([0-9]+)\s*(?:cm|厘米).*?宽[：:\s]*([0-9]+)\s*(?:cm|厘米).*?高[：:\s]*([0-9]+)\s*(?:cm|厘米)",
        r"(?:length|packageLength)[\"'：:\s]*([0-9]+).*?(?:width|packageWidth)[\"'：:\s]*([0-9]+).*?(?:height|packageHeight)[\"'：:\s]*([0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None, None, None


def fetch_1688_public_info(url: str, timeout: int = 15) -> ProductPageInfo:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or "1688.com" not in parsed.netloc:
        return ProductPageInfo(ok=False, error="请输入有效的 1688 商品链接。")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        return ProductPageInfo(ok=False, error=f"无法读取该 1688 页面：{exc.__class__.__name__}")

    content = response.text
    title = _extract_title(content)
    description = (
        _extract_jsonish_value(content, ("description", "desc", "detail", "shortDescription"))
        or _extract_meta(content, "description")
        or _extract_meta(content, "og:description")
    )
    length, width, height = _extract_dimensions(content)
    weight = _extract_weight(content)

    if not any([title, description, weight, length]):
        content_hint = _clean_text(content[:300])
        return ProductPageInfo(
            ok=False,
            error=(
                "页面可访问，但没有识别到公开标题、描述、重量或尺寸。"
                "这通常表示 1688 返回的是动态空壳、登录/风控页，或字段不在 HTML 里。"
                f"页面开头：{content_hint[:120]}"
            ),
        )

    return ProductPageInfo(
        ok=True,
        title=title,
        description=description,
        weight_kg=weight,
        length_cm=length,
        width_cm=width,
        height_cm=height,
    )
