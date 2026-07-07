from __future__ import annotations

import hmac
import json
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Optional

import streamlit as st
from dotenv import load_dotenv

from ali1688_helper import fetch_1688_public_info
from deepseek_client import DeepSeekError, deepseek_configured, translate_product_to_russian
from excel_template import (
    build_common_template_values,
    build_excel_sku,
    fill_official_excel_template_rows,
    get_template_fields,
)
from utils import extract_1688_offer_id
from validators import (
    validate_image_urls,
    validate_package_dimensions,
    validate_price,
    validate_weight,
)


load_dotenv()
st.set_page_config(page_title="AliExpress Russia Excel 模版填充工具", layout="wide")


def get_secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value or os.getenv(name, default) or "")


def sync_streamlit_secrets_to_env(names: list[str]) -> None:
    for name in names:
        value = get_secret_or_env(name)
        if value and not os.getenv(name):
            os.environ[name] = value


def require_login() -> None:
    password = get_secret_or_env("APP_PASSWORD")
    if not password:
        st.error("未配置 APP_PASSWORD。请先在 .env 或 Streamlit Secrets 中设置登录密码。")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("AliExpress Russia Excel 模版填充工具")
    st.subheader("登录")
    entered_password = st.text_input("访问密码", type="password")
    if st.button("登录", type="primary"):
        if hmac.compare_digest(entered_password, password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密码不正确。")
    st.stop()


sync_streamlit_secrets_to_env(["DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DRY_RUN"])
require_login()

st.title("AliExpress Russia Excel 模版填充工具")

PRODUCT_FORM_DEFAULTS: dict[str, Any] = {
    "source_url": "",
    "cn_title": "",
    "cn_description": "",
    "ru_title": "",
    "ru_description": "",
    "en_title": "",
    "en_description": "",
    "image_urls_raw": "",
    "price": "1.00",
    "discount_price": "",
    "inventory": 1,
}

if st.session_state.pop("reset_product_form_pending", False):
    for default_key, default_value in PRODUCT_FORM_DEFAULTS.items():
        st.session_state[default_key] = default_value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(clean_text(item) for item in value if clean_text(item))
    if isinstance(value, dict):
        for key in ("name", "value", "title", "text", "label", "propValue"):
            if value.get(key):
                return clean_text(value[key])
        return ""
    return str(value).strip()


def normalize_field_name(value: str) -> str:
    value = re.sub(r"\*", "", value or "")
    value = re.sub(r"\([^)]*\)", "", value)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def choose_option(raw_value: str, options: list[str]) -> str:
    if not raw_value or not options:
        return ""
    raw_normalized = normalize_field_name(raw_value)
    for option in options:
        if raw_value == option:
            return option
    for option in options:
        option_normalized = normalize_field_name(option)
        if raw_normalized and raw_normalized == option_normalized:
            return option
    for option in options:
        option_normalized = normalize_field_name(option)
        if raw_normalized and (raw_normalized in option_normalized or option_normalized in raw_normalized):
            return option
    return ""


FIELD_ALIASES: dict[str, list[str]] = {
    "brand": ["品牌", "牌子", "brandname"],
    "brandname": ["品牌", "牌子", "brand"],
    "material": ["材质", "面料", "成分", "主面料", "fabric", "composition"],
    "fabric": ["材质", "面料", "成分", "material"],
    "color": ["颜色", "colour", "花色", "色号"],
    "colour": ["颜色", "color", "花色", "色号"],
    "size": ["尺码", "尺寸", "规格", "码数"],
    "gender": ["性别", "适用性别", "男女", "人群"],
    "departmentname": ["性别", "适用性别", "男女", "人群", "gender"],
    "style": ["风格", "款式", "类型"],
    "type": ["类型", "款式", "类别"],
    "itemtype": ["类型", "款式", "类别"],
    "patterntype": ["图案", "印花", "花型"],
    "pattern": ["图案", "印花", "花型"],
    "sleevelength": ["袖长"],
    "sleevestyle": ["袖型"],
    "collar": ["领型", "领口"],
    "hooded": ["连帽", "帽子"],
    "thickness": ["厚度", "薄厚"],
    "season": ["季节", "适用季节"],
    "age": ["年龄", "适用年龄"],
    "fit": ["版型", "适合"],
    "closuretype": ["闭合方式", "门襟", "拉链"],
    "decoration": ["装饰", "工艺"],
    "origin": ["产地", "生产地"],
}


VALUE_ALIASES: dict[str, list[str]] = {
    "men": ["男", "男士", "男性"],
    "women": ["女", "女士", "女性"],
    "unisex": ["男女", "通用", "中性"],
    "cotton": ["棉", "纯棉", "全棉"],
    "polyester": ["聚酯", "涤纶", "聚酯纤维"],
    "spandex": ["氨纶", "弹力"],
    "hooded": ["连帽", "帽衫"],
    "regular": ["常规", "普通"],
    "casual": ["休闲"],
    "solid": ["纯色"],
    "print": ["印花", "图案"],
    "zipper": ["拉链"],
    "pullover": ["套头"],
    "spring": ["春"],
    "summer": ["夏"],
    "autumn": ["秋"],
    "winter": ["冬", "加绒", "保暖"],
}


def option_from_context(options: list[str], context: str) -> str:
    normalized_context = normalize_field_name(context)
    for option in options:
        option_normalized = normalize_field_name(option)
        if option_normalized and option_normalized in normalized_context:
            return option
        for alias in VALUE_ALIASES.get(option_normalized, []):
            if normalize_field_name(alias) in normalized_context:
                return option
    return ""


def first_price_from_json(imported: dict[str, Any]) -> str:
    price_ranges = imported.get("price_ranges") or []
    if isinstance(price_ranges, list):
        for item in price_ranges:
            if isinstance(item, dict) and item.get("price_cny"):
                return clean_text(item["price_cny"])
    skus = imported.get("skus") or []
    if isinstance(skus, list):
        for sku in skus:
            if isinstance(sku, dict) and sku.get("price_cny"):
                return clean_text(sku["price_cny"])
    return ""


def inventory_from_json(imported: dict[str, Any]) -> Optional[int]:
    skus = imported.get("skus") or []
    stocks: list[int] = []
    if isinstance(skus, list):
        for sku in skus:
            if not isinstance(sku, dict):
                continue
            try:
                stock = int(float(sku.get("stock")))
            except (TypeError, ValueError):
                continue
            if stock >= 0:
                stocks.append(stock)
    if not stocks:
        return None
    return max(1, sum(stocks))


def attribute_map_from_json(imported: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in imported.get("attributes") or []:
        if not isinstance(item, dict):
            continue
        name = clean_text(item.get("name"))
        value = clean_text(item.get("value"))
        if name and value:
            result[normalize_field_name(name)] = value

    for sku in imported.get("skus") or []:
        if not isinstance(sku, dict):
            continue
        props = sku.get("props") or {}
        if isinstance(props, dict):
            for name, value in props.items():
                clean_name = clean_text(name)
                clean_value = clean_text(value)
                if clean_name and clean_value:
                    result.setdefault(normalize_field_name(clean_name), clean_value)
        elif isinstance(props, list):
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                name = clean_text(prop.get("name"))
                value = clean_text(prop.get("value"))
                if name and value:
                    result.setdefault(normalize_field_name(name), value)
    return result


def value_for_template_field(
    field: dict[str, Any],
    attributes: dict[str, str],
    context: str,
    category_text: str,
) -> str:
    header = field["header"]
    normalized_header = normalize_field_name(header)

    if "类目" in header or "category" in normalized_header:
        return category_text

    lookup_keys = [normalized_header, *FIELD_ALIASES.get(normalized_header, [])]
    for lookup_key in lookup_keys:
        normalized_lookup = normalize_field_name(lookup_key)
        if normalized_lookup in attributes:
            return attributes[normalized_lookup]

    for attr_name, attr_value in attributes.items():
        if not attr_name:
            continue
        if attr_name in normalized_header or normalized_header in attr_name:
            return attr_value
        for alias in FIELD_ALIASES.get(normalized_header, []):
            normalized_alias = normalize_field_name(alias)
            if normalized_alias and (normalized_alias in attr_name or attr_name in normalized_alias):
                return attr_value

    if field["options"]:
        return option_from_context(field["options"], context)

    return ""


def auto_fill_template_fields_from_json(imported: dict[str, Any], fields: list[dict[str, Any]]) -> int:
    attributes = attribute_map_from_json(imported)
    category_path = imported.get("category_path") or []
    category_text = " > ".join(clean_text(item) for item in category_path if clean_text(item)) if isinstance(category_path, list) else ""
    context_parts = [
        clean_text(imported.get("title")),
        clean_text(imported.get("description")),
        clean_text(imported.get("attributes")),
        clean_text(imported.get("skus")),
    ]
    context = " ".join(part for part in context_parts if part)
    filled_count = 0

    for field in fields:
        header = field["header"]
        key = f"excel_{field['column']}_{header}"
        value = value_for_template_field(field, attributes, context, category_text)

        if not value:
            continue

        if field["options"]:
            option = choose_option(value, field["options"]) or option_from_context(field["options"], f"{value} {context}")
            if not option:
                continue
            value = option

        st.session_state[key] = value
        filled_count += 1

    return filled_count


def template_preview_rows(fields: list[dict[str, Any]], values: dict[str, Any], filled_only: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in fields:
        value = values.get(field["header"], "")
        if filled_only and value in (None, ""):
            continue
        rows.append(
            {
                "列": field["letter"],
                "字段": field["header"],
                "必填": "是" if field["required"] else "否",
                "分组": field["group"],
                "写入值": value,
            }
        )
    return rows


def render_product_visual_preview(title: str, description: str, images: list[str], price_value: str, inventory_value: int) -> None:
    summary_col, image_col = st.columns([1.2, 1])
    with summary_col:
        st.write("商品预览")
        st.text_input("预览标题", value=title, disabled=True)
        st.text_area("预览描述", value=description, height=120, disabled=True)
        price_col, inventory_col = st.columns(2)
        price_col.metric("价格, CNY", price_value or "-")
        inventory_col.metric("库存", inventory_value)
    with image_col:
        st.write("图片预览")
        if images:
            st.image(images[:6], width=120)
        else:
            st.info("还没有图片。")


PROTECTED_AI_FIELD_KEYWORDS = (
    "主图",
    "图片",
    "image",
    "photo",
    "pic",
    "sku",
    "spu",
    "条形码",
    "型号",
    "价格",
    "折扣",
    "库存",
    "inventory",
    "price",
    "包装",
    "重量",
    "长度",
    "宽度",
    "高度",
    "weight",
    "length",
    "width",
    "height",
    "订单处理",
    "运输",
    "shipping",
)


def is_ai_protected_field(header: str) -> bool:
    normalized_header = normalize_field_name(header)
    return any(normalize_field_name(keyword) in normalized_header for keyword in PROTECTED_AI_FIELD_KEYWORDS)


def ai_editable_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [field for field in fields if not is_ai_protected_field(field["header"])]


def apply_template_values_to_session(template_values: dict[str, Any], fields: list[dict[str, Any]]) -> int:
    filled_count = 0
    for field in fields:
        header = field["header"]
        if is_ai_protected_field(header):
            continue
        if header not in template_values:
            continue
        value = clean_text(template_values.get(header))
        if not value:
            continue
        if field["options"]:
            option = choose_option(value, field["options"])
            if not option:
                continue
            value = option
        st.session_state[f"excel_{field['column']}_{header}"] = value
        filled_count += 1
    return filled_count


with st.expander("使用说明", expanded=True):
    st.write(
        "先在俄罗斯速卖通后台选好品类并下载官方 Excel 模版，然后在这里上传模版。"
        "页面会自动识别不同品类模版的字段、必填项和下拉选项，填写第 4 行后生成可下载的 Excel。"
    )
    st.warning(
        "上传 Chrome 插件导出的 1688 JSON 后，页面会尽量自动预填标题、描述、图片、价格、库存、包装尺寸和模版属性字段。"
        "配置 DeepSeek 后，可以一键翻译成俄语并回填模版字段。"
    )

st.subheader("1. 上传官方 Excel 模版")
template_file = st.file_uploader("上传 AliExpress Russia 后台下载的品类 Excel 模版（.xlsx）", type=["xlsx"])
if "product_rows" not in st.session_state:
    st.session_state["product_rows"] = []
if template_file is not None:
    current_template_hash = hashlib.sha256(template_file.getvalue()).hexdigest()
    if st.session_state.get("template_hash") not in (None, current_template_hash):
        st.session_state["product_rows"] = []
        st.session_state.pop("generated_excel_path", None)
        st.info("检测到你更换了 Excel 模版，已清空之前确认的商品列表。")
    st.session_state["template_hash"] = current_template_hash

st.subheader("2. 商品来源")

json_file = st.file_uploader("可选：上传 Chrome 插件导出的 1688_product.json", type=["json"])
if st.button("导入 1688 JSON"):
    if json_file is None:
        st.error("请先上传 1688_product.json。")
    else:
        try:
            imported = json.loads(json_file.getvalue().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(f"JSON 文件无法解析：{exc}")
        else:
            st.session_state["last_imported_1688_json"] = imported
            title = clean_text(imported.get("title"))
            description = clean_text(imported.get("description"))
            st.session_state["source_url"] = imported.get("url", "")
            st.session_state["cn_title"] = title
            st.session_state["cn_description"] = description
            st.session_state["ru_title"] = title
            st.session_state["ru_description"] = description
            images = imported.get("images") or []
            detail_images = imported.get("detail_images") or []
            if isinstance(images, list):
                merged_images = [str(url) for url in images if url]
                if isinstance(detail_images, list):
                    merged_images.extend(str(url) for url in detail_images if url and str(url) not in merged_images)
                st.session_state["image_urls_raw"] = "\n".join(merged_images[:6])
            package = imported.get("package") or {}
            if package.get("weight_kg"):
                st.session_state["weight"] = str(package["weight_kg"])
            if package.get("length_cm"):
                st.session_state["package_length"] = int(package["length_cm"])
            if package.get("width_cm"):
                st.session_state["package_width"] = int(package["width_cm"])
            if package.get("height_cm"):
                st.session_state["package_height"] = int(package["height_cm"])
            first_price = first_price_from_json(imported)
            if first_price:
                st.session_state["price"] = first_price
            detected_inventory = inventory_from_json(imported)
            if detected_inventory is not None:
                st.session_state["inventory"] = detected_inventory

            filled_template_fields = 0
            if template_file is not None:
                filled_template_fields = auto_fill_template_fields_from_json(
                    imported,
                    get_template_fields(template_file.getvalue()),
                )

            st.success(
                "已导入 1688 JSON，并自动预填商品信息。"
                f" 已匹配模版字段：{filled_template_fields} 个。"
            )
            st.rerun()

source_url = st.text_input(
    "1688 商品链接",
    placeholder="https://detail.1688.com/offer/123456789.html",
    key="source_url",
)
offer_id = extract_1688_offer_id(source_url)
auto_sku = build_excel_sku(source_url)
if offer_id:
    st.success(f"已识别 1688 offer ID：{offer_id}，将自动生成 SPU/SKU：{auto_sku}")
else:
    st.info(f"未识别 offer ID，将使用时间戳生成 SPU/SKU：{auto_sku}")

if st.button("尝试从 1688 链接提取公开信息"):
    info = fetch_1688_public_info(source_url)
    if not info.ok:
        st.error(info.error)
    else:
        st.session_state["cn_title"] = info.title
        st.session_state["cn_description"] = info.description
        if info.weight_kg:
            st.session_state["weight"] = info.weight_kg
        if info.length_cm:
            st.session_state["package_length"] = info.length_cm
        if info.width_cm:
            st.session_state["package_width"] = info.width_cm
        if info.height_cm:
            st.session_state["package_height"] = info.height_cm
        st.success("已提取公开信息。请检查标题、描述、重量和尺寸是否准确。")

with st.expander("1688 提取结果（中文，仅供你检查和翻译）", expanded=bool(st.session_state.get("cn_title"))):
    st.text_input("提取到的中文标题", key="cn_title")
    st.text_area("提取到的中文描述", key="cn_description", height=100)
    st.caption("你可以先检查插件提取到的中文内容，再调用 DeepSeek 翻译成俄语并回填。")

st.subheader("3. DeepSeek 俄语翻译")
translate_col1, translate_col2 = st.columns([1, 2])
with translate_col1:
    translate_with_deepseek = st.button("调用 DeepSeek 翻译并回填")
with translate_col2:
    if deepseek_configured():
        st.success("已检测到 DEEPSEEK_API_KEY。")
    else:
        st.warning("未检测到 DEEPSEEK_API_KEY。请先在 .env 中配置。")

if translate_with_deepseek:
    imported_json = st.session_state.get("last_imported_1688_json")
    if not imported_json:
        st.error("请先上传并导入 1688 JSON。")
    else:
        try:
            template_fields_for_ai = get_template_fields(template_file.getvalue()) if template_file is not None else []
            editable_template_fields = ai_editable_fields(template_fields_for_ai)
            preserved_image_urls_raw = st.session_state.get("image_urls_raw", "")
            with st.spinner("DeepSeek 正在翻译并匹配模版字段..."):
                translation = translate_product_to_russian(
                    product_json=imported_json,
                    fields=editable_template_fields,
                )
        except DeepSeekError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"调用 DeepSeek 失败：{exc}")
        else:
            st.session_state["last_deepseek_translation"] = translation
            if translation.get("ru_title"):
                st.session_state["ru_title"] = translation["ru_title"]
            if translation.get("ru_description"):
                st.session_state["ru_description"] = translation["ru_description"]
            filled_count = 0
            if editable_template_fields:
                filled_count = apply_template_values_to_session(
                    translation.get("template_values") or {},
                    editable_template_fields,
                )
            st.session_state["image_urls_raw"] = preserved_image_urls_raw
            st.success(f"DeepSeek 已回填俄语标题/描述，并匹配模版字段：{filled_count} 个。")
            st.rerun()

st.subheader("4. 商品基础信息")
col1, col2 = st.columns(2)
with col1:
    ru_title = st.text_input("产品名称（俄语）", key="ru_title")
    ru_description = st.text_area("描述（俄语）", height=140, key="ru_description")
with col2:
    en_title = st.text_input("产品名称（英语，可选）", key="en_title")
    en_description = st.text_area("描述（英语，可选）", height=140, key="en_description")

st.subheader("5. 图片")
image_urls_raw = st.text_area("图片直链，每行一个。第一行会写入主图，最多 6 张。", height=150, key="image_urls_raw")
image_urls = [line.strip() for line in image_urls_raw.splitlines() if line.strip()]

st.subheader("6. 价格与库存")
col1, col2, col3 = st.columns(3)
with col1:
    price = st.text_input("价格, CNY", value="1.00", key="price")
with col2:
    discount_price = st.text_input("折扣价, CNY（可选）", value="", key="discount_price")
with col3:
    inventory = st.number_input("库存", min_value=0, step=1, value=1, key="inventory")

st.subheader("7. 包装与运输")
col1, col2, col3 = st.columns(3)
with col1:
    shipping_lead_time = st.number_input("订单处理时间（天）", min_value=1, max_value=30, step=1, value=5, key="shipping_lead_time")
with col2:
    weight = st.text_input("包装重量（公斤）", value="1", key="weight")
with col3:
    package_length = st.number_input("包装长度（厘米）", min_value=1, max_value=700, step=1, value=30, key="package_length")

col4, col5 = st.columns(2)
with col4:
    package_width = st.number_input("包装宽度（厘米）", min_value=1, max_value=700, step=1, value=20, key="package_width")
with col5:
    package_height = st.number_input("包装高度（厘米）", min_value=1, max_value=700, step=1, value=10, key="package_height")


def render_template_field(field: dict[str, Any], required: bool) -> Any:
    header = field["header"]
    key = f"excel_{field['column']}_{header}"
    label = f"{field['letter']}列 - {header}"
    if field["note"]:
        st.caption(field["note"])
    if field["options"]:
        options = field["options"] if required else [""] + field["options"]
        default_index = 0
        if "CN(Origin)" in options:
            default_index = options.index("CN(Origin)")
        return st.selectbox(label, options, index=default_index, key=key)
    return st.text_input(label, value="", key=key)


dynamic_values: dict[str, Any] = {}
fields: list[dict[str, Any]] = []
common_values: dict[str, Any] = {}
required_fields: list[dict[str, Any]] = []

if template_file is not None:
    st.subheader("8. 当前品类模版字段")
    template_bytes = template_file.getvalue()
    fields = get_template_fields(template_bytes)
    if st.session_state.get("last_imported_1688_json") and st.button("用已导入 JSON 重新预填模版字段"):
        filled_template_fields = auto_fill_template_fields_from_json(
            st.session_state["last_imported_1688_json"],
            fields,
        )
        st.success(f"已重新预填模版字段：{filled_template_fields} 个。")
        st.rerun()

    common_values = build_common_template_values(
        fields=fields,
        source_url=source_url,
        ru_title=ru_title,
        en_title=en_title,
        ru_description=ru_description,
        en_description=en_description,
        image_urls=image_urls,
        price=price,
        discount_price=discount_price,
        inventory=int(inventory),
        shipping_lead_time=int(shipping_lead_time),
        weight=weight,
        package_length=int(package_length),
        package_width=int(package_width),
        package_height=int(package_height),
    )

    auto_headers = set(common_values)
    required_fields = [field for field in fields if field["required"] and field["header"] not in auto_headers]
    optional_fields = [
        field
        for field in fields
        if not field["required"] and field["header"] not in auto_headers and field["header"] != "None"
    ]

    st.write(f"已识别字段：{len(fields)} 个；还需要你填写的必填字段：{len(required_fields)} 个。")

    if required_fields:
        st.write("必填字段")
        for field in required_fields:
            dynamic_values[field["header"]] = render_template_field(field, required=True)
    else:
        st.success("当前模版的必填字段已经都能从上方表单自动带入。")

    with st.expander("可选字段（按需填写）", expanded=False):
        for field in optional_fields:
            value = render_template_field(field, required=False)
            if value not in (None, ""):
                dynamic_values[field["header"]] = value

    current_preview_values = {**common_values, **dynamic_values}
    st.subheader("9. 自动导入结果预览")
    render_product_visual_preview(
        title=ru_title,
        description=ru_description,
        images=image_urls,
        price_value=price,
        inventory_value=int(inventory),
    )
    preview_tab1, preview_tab2 = st.tabs(["已填写字段", "完整模板列"])
    with preview_tab1:
        filled_preview_rows = template_preview_rows(fields, current_preview_values, filled_only=True)
        st.write(f"当前将写入字段：{len(filled_preview_rows)} 个。")
        st.dataframe(filled_preview_rows, use_container_width=True, hide_index=True)
    with preview_tab2:
        st.dataframe(template_preview_rows(fields, current_preview_values, filled_only=False), use_container_width=True, hide_index=True)
else:
    st.info("请先上传官方 Excel 模版。上传后会自动显示该品类需要填写的字段。")


def validate_current_product() -> list[str]:
    errors: list[str] = []
    errors.extend(validate_image_urls(image_urls))
    errors.extend(validate_price(price, "价格"))
    if discount_price.strip():
        errors.extend(validate_price(discount_price, "折扣价"))
    errors.extend(validate_package_dimensions(package_length, package_width, package_height))
    errors.extend(validate_weight(weight))
    if not ru_title.strip():
        errors.append("产品名称（俄语）不能为空。")
    if not ru_description.strip():
        errors.append("描述（俄语）不能为空。")
    for field in required_fields:
        if dynamic_values.get(field["header"]) in (None, ""):
            errors.append(f"{field['header']} 是当前模版的必填字段。")
    return errors


st.subheader("10. 确认商品并生成 Excel")
st.write(f"当前已确认商品：{len(st.session_state['product_rows'])} 个。")

action_col1, action_col2, action_col3 = st.columns([1.4, 1.4, 1])
with action_col1:
    add_current_product = st.button("确认添加当前商品", type="primary")
with action_col2:
    add_and_continue = st.button("确认添加，并继续下一个")
with action_col3:
    clear_products = st.button("清空已确认商品")

if clear_products:
    st.session_state["product_rows"] = []
    st.session_state.pop("generated_excel_path", None)
    st.success("已清空已确认商品列表。")
    st.rerun()

if add_current_product or add_and_continue:
    if template_file is None:
        st.error("请先上传官方 Excel 模版。")
    else:
        errors = validate_current_product()

        if errors:
            for error in errors:
                st.error(error)
        else:
            values = {**common_values, **dynamic_values}
            st.session_state["product_rows"].append(
                {
                    "offer_id": offer_id or "",
                    "sku": auto_sku,
                    "title": ru_title,
                    "price": price,
                    "inventory": int(inventory),
                    "values": values,
                }
            )
            st.session_state.pop("generated_excel_path", None)
            st.success(f"已确认添加：{ru_title}")
            if add_and_continue:
                st.session_state["reset_product_form_pending"] = True
            st.rerun()

if st.session_state["product_rows"]:
    st.write("已确认商品列表")
    st.dataframe(
        [
            {
                "序号": index,
                "1688 offer ID": row["offer_id"],
                "SKU": row["sku"],
                "产品名称（俄语）": row["title"],
                "价格": row["price"],
                "库存": row["inventory"],
            }
            for index, row in enumerate(st.session_state["product_rows"], start=1)
        ],
        use_container_width=True,
        hide_index=True,
    )

    if fields:
        with st.expander("已确认商品的 Excel 行预览", expanded=True):
            all_headers = [field["header"] for field in fields]
            selected_headers = [
                header
                for header in all_headers
                if any(row["values"].get(header) not in (None, "") for row in st.session_state["product_rows"])
            ]
            preview_rows = []
            for index, row in enumerate(st.session_state["product_rows"], start=4):
                preview_row = {"Excel 行": index}
                for header in selected_headers:
                    preview_row[header] = row["values"].get(header, "")
                preview_rows.append(preview_row)
            st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    if st.button("生成已确认商品 Excel"):
        if template_file is None:
            st.error("请先上传官方 Excel 模版。")
        else:
            output_name = f"filled_aliexpress_template_{len(st.session_state['product_rows'])}_items.xlsx"
            output_path = Path("output") / output_name
            saved_path = fill_official_excel_template_rows(
                template_file.getvalue(),
                [row["values"] for row in st.session_state["product_rows"]],
                output_path,
            )
            st.session_state["generated_excel_path"] = str(saved_path)
            st.success(f"已生成 Excel：{saved_path}")

    generated_path = st.session_state.get("generated_excel_path")
    if generated_path:
        saved_path = Path(generated_path)
        if saved_path.exists():
            with saved_path.open("rb") as fh:
                st.download_button(
                    "下载已填写 Excel",
                    data=fh,
                    file_name=saved_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
else:
    st.info("填写完当前商品后，先点击“确认添加当前商品”。同一个品类可以连续添加多个商品，再统一生成 Excel。")
