from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


class DeepSeekError(RuntimeError):
    pass


def deepseek_configured() -> bool:
    load_dotenv()
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _compact_product_payload(product_json: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": product_json.get("title", ""),
        "description": product_json.get("description", ""),
        "attributes": (product_json.get("attributes") or [])[:80],
        "skus": (product_json.get("skus") or [])[:80],
        "price_ranges": product_json.get("price_ranges") or [],
        "category_path": product_json.get("category_path") or [],
        "package": product_json.get("package") or {},
    }


def _compact_template_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact_fields: list[dict[str, Any]] = []
    for field in fields:
        options = field.get("options") or []
        compact_fields.append(
            {
                "header": field["header"],
                "required": bool(field.get("required")),
                "note": field.get("note", ""),
                "options": options[:80],
            }
        )
    return compact_fields


LISTING_GUIDELINES = (
    "AliExpress Russia listing guidelines to follow: "
    "write clear Russian for buyers; title should describe the product type, key material/style, target user, "
    "and important attributes only; avoid keyword stuffing, repeated words, emojis, ALL CAPS, unsupported brand names, "
    "medical/guaranteed claims, counterfeit claims, extreme promotional language, logistics promises, discounts, or prices. "
    "Description should be useful and factual: product overview, material/features, fit/use cases, package or care notes "
    "when supported by source data. Do not invent certifications, brands, country of origin, warranty, shipping speed, "
    "discounts, prices, inventory, image URLs, SKU/SPU IDs, or package dimensions."
)


def _extract_json_object(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise DeepSeekError("DeepSeek 返回内容不是 JSON。")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise DeepSeekError("DeepSeek 返回 JSON 顶层不是对象。")
    return data


def translate_product_to_russian(
    *,
    product_json: dict[str, Any],
    fields: list[dict[str, Any]],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 60,
) -> dict[str, Any]:
    load_dotenv()
    resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not resolved_api_key:
        raise DeepSeekError("请先在 .env 中配置 DEEPSEEK_API_KEY。")

    resolved_base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")
    resolved_model = model or os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL

    payload = {
        "product": _compact_product_payload(product_json),
        "template_fields": _compact_template_fields(fields),
    }
    system_prompt = (
        "You are an AliExpress Russia listing assistant. Translate Chinese 1688 product content into Russian "
        "and map it into the provided AliExpress Excel template fields. Return only valid json. "
        f"{LISTING_GUIDELINES}"
    )
    user_prompt = (
        "Return json with this exact shape: "
        '{"ru_title": string, "ru_description": string, "template_values": object}. '
        "Rules: ru_title must be a compliant Russian marketplace title, preferably 80-140 characters when possible, "
        "without price, shipping promises, emojis, excessive punctuation, unsupported brands, or keyword spam. "
        "ru_description must be natural Russian, buyer-facing, concise, and structured in short paragraphs or bullet-like lines. "
        "For template_values, keys must be exact template field headers from template_fields. If a field has options, use one exact "
        "option from the options list or omit it. For free-text translation fields, translate useful product attributes into Russian. "
        "Only fill fields that require language/attribute interpretation. Do not fill or change image, price, inventory, SKU/SPU, "
        "shipping, package weight, package length, package width, or package height fields. "
        "Do not invent any fact not supported by the source data. Here is the source json:\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )

    response = requests.post(
        f"{resolved_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise DeepSeekError(f"DeepSeek 请求失败：HTTP {response.status_code} - {response.text[:500]}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError(f"DeepSeek 响应格式异常：{data}") from exc

    result = _extract_json_object(content)
    template_values = result.get("template_values") or {}
    if not isinstance(template_values, dict):
        template_values = {}
    return {
        "ru_title": str(result.get("ru_title") or "").strip(),
        "ru_description": str(result.get("ru_description") or "").strip(),
        "template_values": template_values,
        "model": resolved_model,
    }
