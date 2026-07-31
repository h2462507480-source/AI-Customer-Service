from __future__ import annotations

import json
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from .importer import iter_source_rows
from .models import Base, PhoneModelSupport, UnknownPhoneModelQuery
from .normalization import (
    extract_brand_hint,
    extract_material_hint,
    extract_model_key,
    normalize,
    normalize_material,
    split_model_group,
    strip_brand_prefix,
)

UNAVAILABLE_MARKERS = ("未到货", "待到货", "缺货", "无货", "停产", "下架", "不支持")


class PhoneModelService:
    def __init__(self, session_factory: Callable[[], Session], engine):
        self.session_factory = session_factory
        self.engine = engine
        Base.metadata.create_all(engine)

    def get_session(self) -> Session:
        return self.session_factory()

    @staticmethod
    def _is_supported(stock_status: str) -> bool:
        return not any(marker in str(stock_status or "") for marker in UNAVAILABLE_MARKERS)

    def import_file(self, shop_key: str, path: str | Path) -> dict[str, int]:
        source = Path(path)
        stats = {"rows": 0, "models": 0, "created": 0, "updated": 0, "skipped": 0}
        with self.get_session() as session:
            for row in iter_source_rows(source):
                stats["rows"] += 1
                material = normalize_material(row.get("material"))
                model_group = row.get("model_group", "")
                if not material or not model_group:
                    stats["skipped"] += 1
                    continue
                parsed_models = split_model_group(row.get("brand"), model_group)
                if not parsed_models:
                    stats["skipped"] += 1
                    continue
                for parsed in parsed_models:
                    stats["models"] += 1
                    stmt = select(PhoneModelSupport).where(
                        and_(
                            PhoneModelSupport.shop_key == str(shop_key),
                            PhoneModelSupport.material_name == material,
                            PhoneModelSupport.brand == parsed.brand,
                            PhoneModelSupport.normalized_model == parsed.normalized_model,
                        )
                    )
                    existing = session.scalar(stmt)
                    values = {
                        "model_name": parsed.model_name,
                        "aliases_json": json.dumps(parsed.aliases, ensure_ascii=False),
                        "supported": self._is_supported(str(row.get("stock_status", ""))),
                        "stock_status": str(row.get("stock_status", "")),
                        "source_file": source.name,
                        "updated_at": datetime.now(),
                    }
                    if existing:
                        for key, value in values.items():
                            setattr(existing, key, value)
                        stats["updated"] += 1
                    else:
                        session.add(
                            PhoneModelSupport(
                                shop_key=str(shop_key),
                                material_name=material,
                                brand=parsed.brand,
                                normalized_model=parsed.normalized_model,
                                **values,
                            )
                        )
                        stats["created"] += 1
            session.commit()
        return stats

    def query_support(
        self,
        shop_key: str,
        model: str,
        *,
        brand_hint: str = "",
        material_hint: str = "",
        raw_query: str = "",
    ) -> dict[str, Any]:
        embedded_brand = extract_brand_hint(model)
        brand = embedded_brand or extract_brand_hint(brand_hint or raw_query)
        clean_model = strip_brand_prefix(str(model), embedded_brand) if embedded_brand else str(model)
        model_key = normalize(clean_model)
        material = normalize_material(material_hint) if material_hint else extract_material_hint(raw_query)
        if not model_key and raw_query:
            model_key = extract_model_key(raw_query, brand, material)
        with self.get_session() as session:
            conditions = [
                PhoneModelSupport.shop_key == str(shop_key),
                PhoneModelSupport.normalized_model == model_key,
            ]
            if brand:
                conditions.append(PhoneModelSupport.brand == brand)
            if material:
                conditions.append(PhoneModelSupport.material_name == material)
            rows = list(session.scalars(select(PhoneModelSupport).where(and_(*conditions))))
            if not rows and brand == "VIVO":
                conditions = [
                    PhoneModelSupport.shop_key == str(shop_key),
                    PhoneModelSupport.normalized_model == model_key,
                    PhoneModelSupport.brand.in_(["VIVO", "IQOO"]),
                ]
                if material:
                    conditions.append(PhoneModelSupport.material_name == material)
                rows = list(session.scalars(select(PhoneModelSupport).where(and_(*conditions))))
            if rows:
                return {
                    "status": "matched",
                    "brand": rows[0].brand,
                    "model": rows[0].model_name,
                    "materials": [
                        {
                            "material_name": row.material_name,
                            "supported": row.supported,
                            "stock_status": row.stock_status,
                        }
                        for row in sorted(rows, key=lambda item: item.material_name)
                    ],
                }
            suggestions = self._find_similar(session, str(shop_key), model_key, brand)
            if suggestions:
                return {"status": "ambiguous", "brand": brand, "model": model, "suggestions": suggestions}
            self._record_unknown(session, str(shop_key), brand, model, model_key, raw_query)
            session.commit()
            return {"status": "not_found", "brand": brand, "model": model}

    def query_text(self, shop_key: str, raw_query: str) -> dict[str, Any]:
        brand = extract_brand_hint(raw_query)
        material = extract_material_hint(raw_query)
        model = extract_model_key(raw_query, brand, material)
        return self.query_support(
            shop_key,
            model,
            brand_hint=brand,
            material_hint=material,
            raw_query=raw_query,
        )

    @staticmethod
    def format_customer_reply(result: dict[str, Any]) -> str:
        status = result.get("status")
        if status == "matched":
            available = [m["material_name"] for m in result["materials"] if m["supported"]]
            unavailable = [m["material_name"] for m in result["materials"] if not m["supported"]]
            if available and unavailable:
                return f"亲，{result['brand']} {result['model']}目前{'、'.join(available)}有，{'、'.join(unavailable)}暂时没有哦。"
            if available:
                return f"亲，{result['brand']} {result['model']}目前{'、'.join(available)}有哦。"
            return f"亲，{result['brand']} {result['model']}目前暂时没有哦。"
        if status == "ambiguous":
            return f"亲，请确认具体型号：{'、'.join(result.get('suggestions', []))}。"
        return "亲，这个型号我暂时没查到，我帮您转人工确认一下哦。"

    @staticmethod
    def _find_similar(session: Session, shop_key: str, model_key: str, brand: str) -> list[str]:
        conditions = [PhoneModelSupport.shop_key == shop_key]
        if brand:
            conditions.append(PhoneModelSupport.brand == brand)
        candidates = list(session.scalars(select(PhoneModelSupport).where(and_(*conditions))))
        scored: list[tuple[float, str]] = []
        for item in candidates:
            score = SequenceMatcher(None, model_key, item.normalized_model).ratio()
            if score >= 0.6 or model_key in item.normalized_model or item.normalized_model in model_key:
                scored.append((score, item.model_name))
        return [name for _, name in sorted(set(scored), reverse=True)[:5]]

    @staticmethod
    def _record_unknown(
        session: Session,
        shop_key: str,
        brand: str,
        model_name: str,
        normalized_model: str,
        raw_query: str,
    ) -> None:
        stmt = select(UnknownPhoneModelQuery).where(
            and_(
                UnknownPhoneModelQuery.shop_key == shop_key,
                UnknownPhoneModelQuery.brand == brand,
                UnknownPhoneModelQuery.normalized_model == normalized_model,
            )
        )
        existing = session.scalar(stmt)
        if existing:
            existing.query_count += 1
            existing.raw_query = raw_query or existing.raw_query
            existing.last_seen_at = datetime.now()
        else:
            session.add(
                UnknownPhoneModelQuery(
                    shop_key=shop_key,
                    brand=brand,
                    model_name=model_name,
                    normalized_model=normalized_model,
                    raw_query=raw_query,
                )
            )
