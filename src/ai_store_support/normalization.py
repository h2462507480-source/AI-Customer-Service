from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "苹果": ("苹果", "IPHONE", "APPLE"),
    "华为": ("华为", "HUAWEI"),
    "荣耀": ("荣耀", "HONOR"),
    "OPPO": ("OPPO",),
    "VIVO": ("VIVO",),
    "IQOO": ("IQOO", "I QOO"),
    "小米": ("小米", "XIAOMI", "MI"),
    "红米": ("红米", "REDMI"),
    "POCO": ("POCO",),
    "三星": ("三星", "SAMSUNG"),
    "一加": ("一加", "ONEPLUS"),
    "真我": ("真我", "REALME"),
    "魅族": ("魅族", "MEIZU"),
}

MATERIAL_ALIASES: dict[str, tuple[str, ...]] = {
    "FL二合一磨砂二代": ("二合一磨砂二代", "磨砂二代", "磨砂壳", "磨砂"),
    "FL液态直边软壳": ("液态直边软壳", "液态直边", "液态壳", "直边软壳", "液态"),
}

QUESTION_PHRASES = (
    "有没有", "有吗", "支持吗", "支持", "适配吗", "适配", "能做吗", "能做", "能用吗", "能用",
    "这个型号", "该型号", "什么型号", "手机型号", "型号", "手机壳", "保护壳", "壳子", "壳",
    "两个材质", "两种材质", "哪种材质", "什么材质", "材质", "都有吗", "都支持吗", "都",
    "请问", "麻烦查下", "帮我查下", "帮我看看", "查一下", "查下", "看看", "亲",
    "那个", "这个", "刚才", "另外一种", "另一种", "呢", "呀", "啊", "吗", "有", "无",
)


@dataclass(frozen=True)
class ParsedModel:
    brand: str
    model_name: str
    normalized_model: str
    aliases: tuple[str, ...]


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).upper().strip()
    return re.sub(r"[^0-9A-Z\u4e00-\u9fff]+", "", text)


def normalize_material(value: Any) -> str:
    normalized = normalize(value)
    for canonical, aliases in MATERIAL_ALIASES.items():
        if normalized == normalize(canonical):
            return canonical
        if any(normalize(alias) in normalized for alias in aliases):
            return canonical
    return str(value or "").strip()


def detect_brand(text: Any, fallback: str = "") -> str:
    normalized = normalize(text)
    order = ("IQOO", "红米", "POCO", "一加", "真我", "苹果", "华为", "荣耀", "OPPO", "VIVO", "小米", "三星", "魅族")
    for canonical in order:
        if any(normalize(alias) in normalized for alias in BRAND_ALIASES[canonical]):
            return canonical
    fallback_text = str(fallback or "").strip()
    return "" if "/" in fallback_text else fallback_text


def strip_brand_prefix(text: str, brand: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(text or "")).strip(" ()（）[]【】")
    candidates = sorted(set(filter(None, BRAND_ALIASES.get(brand, (brand,)))), key=len, reverse=True)
    for alias in candidates:
        cleaned = re.sub(rf"^\s*{re.escape(alias)}\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ()（）[]【】")


def build_aliases(brand: str, model_name: str, raw_part: str = "") -> set[str]:
    aliases = {normalize(model_name), normalize(raw_part)}
    if brand:
        aliases.add(normalize(f"{brand}{model_name}"))
        for alias in BRAND_ALIASES.get(brand, (brand,)):
            aliases.add(normalize(f"{alias}{model_name}"))
    aliases.discard("")
    return aliases


def split_model_group(brand_column: Any, model_group: Any) -> list[ParsedModel]:
    group = unicodedata.normalize("NFKC", str(model_group or "")).strip()
    if not group:
        return []
    parts = [p.strip() for p in re.split(r"[/／、，,|｜]+", group) if p and p.strip()]
    parsed: list[ParsedModel] = []
    seen: set[tuple[str, str]] = set()
    for part in parts:
        part = re.sub(r"(?:通用|共用)$", "", part, flags=re.IGNORECASE).strip(" ()（）[]【】")
        if not part:
            continue
        brand = detect_brand(part, fallback=str(brand_column or "").strip())
        model_name = re.sub(r"(?:通用|共用)$", "", strip_brand_prefix(part, brand), flags=re.IGNORECASE).strip()
        normalized_model = normalize(model_name)
        if not normalized_model or (brand, normalized_model) in seen:
            continue
        seen.add((brand, normalized_model))
        parsed.append(ParsedModel(brand, model_name, normalized_model, tuple(sorted(build_aliases(brand, model_name, part)))))
    return parsed


def extract_brand_hint(text: Any) -> str:
    return detect_brand(text)


def extract_material_hint(text: Any) -> str:
    normalized = normalize(text)
    for canonical, aliases in MATERIAL_ALIASES.items():
        if normalize(canonical) in normalized or any(normalize(alias) in normalized for alias in aliases):
            return canonical
    return ""


def extract_model_key(text: Any, brand_hint: str = "", material_hint: str = "") -> str:
    cleaned = unicodedata.normalize("NFKC", str(text or "")).upper()
    for phrase in sorted(QUESTION_PHRASES, key=len, reverse=True):
        cleaned = cleaned.replace(phrase.upper(), "")
    terms = [material_hint, brand_hint]
    terms += [item for aliases in MATERIAL_ALIASES.values() for item in aliases]
    terms += [item for aliases in BRAND_ALIASES.values() for item in aliases]
    for term in sorted(set(filter(None, terms)), key=len, reverse=True):
        cleaned = re.sub(re.escape(str(term).upper()), "", cleaned)
    return normalize(cleaned)
