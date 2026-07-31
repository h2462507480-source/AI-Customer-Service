from __future__ import annotations

import re

from .normalization import extract_brand_hint, extract_material_hint, extract_model_key, normalize

MODEL_QUESTION_MARKERS = (
    "有吗",
    "有没有",
    "支持吗",
    "支持不",
    "适配吗",
    "能做吗",
    "能用吗",
    "这个型号",
    "型号有",
    "型号",
    "手机壳有",
    "壳有",
)


def looks_like_phone_model_query(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    normalized = normalize(raw)
    brand = extract_brand_hint(raw)
    material = extract_material_hint(raw)
    model_key = extract_model_key(raw, brand, material)
    has_question_marker = any(marker in raw for marker in MODEL_QUESTION_MARKERS)
    has_model_shape = bool(re.search(r"[A-Z]*\d+[A-Z0-9]*", normalized))
    if brand and model_key and has_model_shape:
        return True
    if has_question_marker and model_key and has_model_shape:
        return True
    return False
