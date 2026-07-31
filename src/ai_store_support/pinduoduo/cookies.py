from __future__ import annotations

from typing import Any


def normalize_cookies(value: Any) -> dict[str, str]:
    """Normalize a runtime cookie mapping without persisting or logging values."""
    if isinstance(value, dict) and isinstance(value.get("cookies"), (dict, list)):
        value = value["cookies"]
    if isinstance(value, dict):
        result = {str(key): str(item) for key, item in value.items() if str(key) and item is not None}
    elif isinstance(value, list):
        result = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            name, cookie_value = item.get("name"), item.get("value")
            if name is not None and cookie_value is not None:
                result[str(name)] = str(cookie_value)
    else:
        raise ValueError("cookies must be a mapping or browser-export list")
    if not result:
        raise ValueError("no valid cookies supplied")
    return result


def cookie_summary(cookies: dict[str, str]) -> dict[str, object]:
    return {"count": len(cookies), "names": sorted(cookies)}
