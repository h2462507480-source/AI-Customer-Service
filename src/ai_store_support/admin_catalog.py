from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, desc, or_, select

from .admin_core import _ALLOWED_UNKNOWN_STATUSES, _iso, _json_loads
from .config_models import KnowledgeEntry, RoutingRule
from .models import PhoneModelSupport, UnknownPhoneModelQuery


class AdminCatalogMixin:

    def import_models(self, shop_key: str, path: str | Path) -> dict[str, int]:
            if self.engine is None:
                raise RuntimeError("导入型号表需要数据库 engine")
            from .service import PhoneModelService

            return PhoneModelService(self.session_factory, self.engine).import_file(shop_key, path)

    def list_phone_models(
            self,
            shop_key: str,
            *,
            query: str = "",
            brand: str = "",
            material: str = "",
            supported: bool | None = None,
            limit: int = 500,
            offset: int = 0,
        ) -> list[dict[str, Any]]:
            stmt = select(PhoneModelSupport).where(PhoneModelSupport.shop_key == shop_key)
            query = str(query or "").strip()
            if query:
                pattern = f"%{query}%"
                stmt = stmt.where(or_(PhoneModelSupport.model_name.ilike(pattern), PhoneModelSupport.normalized_model.ilike(pattern)))
            if brand:
                stmt = stmt.where(PhoneModelSupport.brand == brand)
            if material:
                stmt = stmt.where(PhoneModelSupport.material_name == material)
            if supported is not None:
                stmt = stmt.where(PhoneModelSupport.supported.is_(supported))
            stmt = stmt.order_by(PhoneModelSupport.brand, PhoneModelSupport.model_name, PhoneModelSupport.material_name).offset(max(0, offset)).limit(max(1, min(limit, 5000)))
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
            return [
                {
                    "id": row.id,
                    "shop_key": row.shop_key,
                    "brand": row.brand,
                    "model_name": row.model_name,
                    "normalized_model": row.normalized_model,
                    "material_name": row.material_name,
                    "supported": row.supported,
                    "stock_status": row.stock_status,
                    "source_file": row.source_file,
                    "updated_at": _iso(row.updated_at),
                }
                for row in rows
            ]

    def update_phone_model(self, row_id: int, *, supported: bool, stock_status: str = "") -> dict[str, Any]:
            with self.session_factory() as session:
                row = session.get(PhoneModelSupport, int(row_id))
                if row is None:
                    raise KeyError(f"型号记录不存在: {row_id}")
                row.supported = bool(supported)
                row.stock_status = str(stock_status or "").strip()
                row.updated_at = datetime.now()
                session.commit()
                return {"id": row.id, "supported": row.supported, "stock_status": row.stock_status}

    def delete_phone_model(self, row_id: int) -> bool:
            with self.session_factory() as session:
                row = session.get(PhoneModelSupport, int(row_id))
                if row is None:
                    return False
                session.delete(row)
                session.commit()
                return True

    def list_unknown_models(self, shop_key: str, *, status: str = "pending", limit: int = 500) -> list[dict[str, Any]]:
            stmt = select(UnknownPhoneModelQuery).where(UnknownPhoneModelQuery.shop_key == shop_key)
            if status and status != "all":
                stmt = stmt.where(UnknownPhoneModelQuery.status == status)
            stmt = stmt.order_by(desc(UnknownPhoneModelQuery.query_count), desc(UnknownPhoneModelQuery.last_seen_at)).limit(max(1, min(limit, 5000)))
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
            return [
                {
                    "id": row.id,
                    "brand": row.brand,
                    "model_name": row.model_name,
                    "normalized_model": row.normalized_model,
                    "raw_query": row.raw_query,
                    "query_count": row.query_count,
                    "status": row.status,
                    "first_seen_at": _iso(row.first_seen_at),
                    "last_seen_at": _iso(row.last_seen_at),
                }
                for row in rows
            ]

    def set_unknown_status(self, row_id: int, status: str) -> None:
            if status not in _ALLOWED_UNKNOWN_STATUSES:
                raise ValueError(f"未知型号状态不合法: {status}")
            with self.session_factory() as session:
                row = session.get(UnknownPhoneModelQuery, int(row_id))
                if row is None:
                    raise KeyError(f"未知型号记录不存在: {row_id}")
                row.status = status
                session.commit()

    def promote_unknown_model(
            self,
            row_id: int,
            *,
            material_name: str,
            supported: bool = True,
            stock_status: str = "",
        ) -> int:
            material_name = str(material_name or "").strip()
            if not material_name:
                raise ValueError("材质不能为空")
            with self.session_factory() as session:
                unknown = session.get(UnknownPhoneModelQuery, int(row_id))
                if unknown is None:
                    raise KeyError(f"未知型号记录不存在: {row_id}")
                existing = session.scalar(
                    select(PhoneModelSupport).where(
                        PhoneModelSupport.shop_key == unknown.shop_key,
                        PhoneModelSupport.material_name == material_name,
                        PhoneModelSupport.brand == unknown.brand,
                        PhoneModelSupport.normalized_model == unknown.normalized_model,
                    )
                )
                if existing is None:
                    existing = PhoneModelSupport(
                        shop_key=unknown.shop_key,
                        material_name=material_name,
                        brand=unknown.brand,
                        model_name=unknown.model_name,
                        normalized_model=unknown.normalized_model,
                        aliases_json="[]",
                        source_file="manual",
                    )
                    session.add(existing)
                existing.model_name = unknown.model_name
                existing.supported = bool(supported)
                existing.stock_status = str(stock_status or "").strip()
                existing.updated_at = datetime.now()
                unknown.status = "resolved"
                session.commit()
                return existing.id

    def import_knowledge(self, shop_key: str, path: str | Path) -> dict[str, int]:
            from .knowledge import KnowledgeService

            return KnowledgeService(self.session_factory).import_file(shop_key, path)

    def list_knowledge(self, shop_key: str, *, query: str = "", enabled: bool | None = None) -> list[dict[str, Any]]:
            stmt = select(KnowledgeEntry).where(KnowledgeEntry.shop_key == shop_key)
            query = str(query or "").strip()
            if query:
                pattern = f"%{query}%"
                stmt = stmt.where(or_(KnowledgeEntry.title.ilike(pattern), KnowledgeEntry.content.ilike(pattern), KnowledgeEntry.tags_json.ilike(pattern)))
            if enabled is not None:
                stmt = stmt.where(KnowledgeEntry.enabled.is_(enabled))
            stmt = stmt.order_by(desc(KnowledgeEntry.priority), KnowledgeEntry.title)
            with self.session_factory() as session:
                rows = list(session.scalars(stmt))
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "tags": _json_loads(row.tags_json, []),
                    "priority": row.priority,
                    "enabled": row.enabled,
                    "direct_reply": row.direct_reply,
                    "updated_at": _iso(row.updated_at),
                }
                for row in rows
            ]

    def save_knowledge(
            self,
            shop_key: str,
            *,
            title: str,
            content: str,
            tags: list[str] | tuple[str, ...] = (),
            priority: int = 0,
            enabled: bool = True,
            direct_reply: bool = True,
            row_id: int | None = None,
        ) -> int:
            title = str(title or "").strip()
            content = str(content or "").strip()
            if not title or not content:
                raise ValueError("知识标题和内容不能为空")
            with self.session_factory() as session:
                row = session.get(KnowledgeEntry, int(row_id)) if row_id else None
                if row is None:
                    row = session.scalar(select(KnowledgeEntry).where(KnowledgeEntry.shop_key == shop_key, KnowledgeEntry.title == title))
                if row is None:
                    row = KnowledgeEntry(shop_key=shop_key, title=title, content=content)
                    session.add(row)
                elif row.shop_key != shop_key:
                    raise ValueError("不能跨店铺修改知识")
                row.title = title
                row.content = content
                row.tags_json = json.dumps([str(item).strip() for item in tags if str(item).strip()], ensure_ascii=False)
                row.priority = int(priority)
                row.enabled = bool(enabled)
                row.direct_reply = bool(direct_reply)
                row.updated_at = datetime.now()
                session.commit()
                return row.id

    def delete_knowledge(self, row_id: int) -> bool:
            with self.session_factory() as session:
                row = session.get(KnowledgeEntry, int(row_id))
                if row is None:
                    return False
                session.delete(row)
                session.commit()
                return True

    def list_rules(self, shop_key: str) -> list[dict[str, Any]]:
            with self.session_factory() as session:
                rows = list(session.scalars(select(RoutingRule).where(RoutingRule.shop_key == shop_key).order_by(desc(RoutingRule.priority), RoutingRule.name)))
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "keywords": _json_loads(row.keywords_json, []),
                    "match_type": row.match_type,
                    "action": row.action,
                    "reply_text": row.reply_text,
                    "reason": row.reason,
                    "target_group": row.target_group,
                    "priority": row.priority,
                    "enabled": row.enabled,
                }
                for row in rows
            ]

    def save_rule(self, shop_key: str, *, name: str, keywords: list[str], action: str, reply_text: str = "", reason: str = "", target_group: str = "", priority: int = 0, enabled: bool = True, row_id: int | None = None) -> int:
            name = str(name or "").strip()
            if not name:
                raise ValueError("规则名称不能为空")
            if action not in {"reply", "handoff", "ignore"}:
                raise ValueError("规匙动作必须是 reply、handoff 或 ignore")
            with self.session_factory() as session:
                row = session.get(RoutingRule, int(row_id)) if row_id else None
                if row is None:
                    row = session.scalar(select(RoutingRule).where(RoutingRule.shop_key == shop_key, RoutingRule.name == name))
                if row is None:
                    row = RoutingRule(shop_key=shop_key, name=name)
                    session.add(row)
                elif row.shop_key != shop_key:
                    raise ValueError("不能跨店铺修改规则")
                row.name = name
                row.keywords_json = json.dumps([str(item).strip() for item in keywords if str(item).strip()], ensure_ascii=False)
                row.action = action
                row.reply_text = str(reply_text or "")
                row.reason = str(reason or "")
                row.target_group = str(target_group or "")
                row.priority = int(priority)
                row.enabled = bool(enabled)
                row.updated_at = datetime.now()
                session.commit()
                return row.id

    def delete_rule(self, row_id: int) -> bool:
            with self.session_factory() as session:
                result = session.execute(delete(RoutingRule).where(RoutingRule.id == int(row_id)))
                session.commit()
                return bool(result.rowcount)
