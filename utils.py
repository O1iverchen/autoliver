from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


OUTPUT_DIR = Path("output")


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def save_json(path: str | Path, data: Any) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def extract_1688_offer_id(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"/offer/(\d+)\.html?(?:\?|$)", url)
    if match:
        return match.group(1)
    return None


def mask_token(token: str | None) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


def now_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")
