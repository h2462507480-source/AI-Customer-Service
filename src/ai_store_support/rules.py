from __future__ import annotations

import json
import re
from typing import Callable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .config_models import RoutingRule
from .normalization import normalize
from .schemas import RuleMatch

DEFAULT_HANDOFF_KEYWORDS = (
    "退款", "退货", "投诉", "平台介入", "差评", "质量问题", "发错型号", "发错货",
    "少件", "漏发", "破损", "赔偿", "补发", "修改地址", "改地址", "催物流",
    "订单异常", "要求补偿", "人工客服", "转人工",
)


class RuleService:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def upsert(
        self,
        *,
        shop_key: str,
        name: str,
        keywords: list[str] | tuple[str, ...],
        action: str,
        match_type: str = "contains",
        reply_text: str = "",
        reason: str = "",
        target_group: str = "",
        priority: int = 0,
        enabled: bool = True,
    ) -> int:
        if action not in {"handoff", "fixed_reply", "ignore"}:
            raise ValueError("action 仅支持 handoff、fixed_reply、ignore")
        if match_type not in {"contains", "exact", "regex"}:
            raise ValueError("match_type 仅支持 contains、exact、regex")
        with self.session_factory() as session:
            row = session.scalar(
                select(RoutingRule).where(
                    RoutingRule.shop_key == shop_key,
                    RoutingRule.name == name,
                )
            )
            if row is None:
                row = RoutingRule(shop_key=shop_key, name=name)
                session.add(row)
            row.keywords_json = json.dumps(list(keywords), ensure_ascii=False)
            row.action = action
            row.match_type = match_type
            row.reply_text = reply_text
            row.reason = reason
            row.target_group = target_group
            row.priority = int(priority)
            row.enabled = bool(enabled)
            session.commit()
            return row.id

    def match(self, shop_key: str, message: str) -> RuleMatch | None:
        text = str(message or "").strip()
        if not text:
            return None
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(RoutingRule)
                    .where(
                        RoutingRule.shop_key == shop_key,
                        RoutingRule.enabled.is_(True),
                    )
                    .order_by(desc(RoutingRule.priority), RoutingRule.id)
                )
            )
        for row in rows:
            keywords = json.loads(row.keywords_json or "[]")
            matched = self._match_keywords(text, keywords, row.match_type)
            if matched:
                return RuleMatch(
                    rule_id=row.id,
                    name=row.name,
                    action=row.action,
                    reply_text=row.reply_text,
                    reason=row.reason or row.name,
                    target_group=row.target_group,
                    matched_keyword=matched,
                )
        default_match = next((keyword for keyword in DEFAULT_HANDOFF_KEYWORDS if keyword in text), "")
        if default_match:
            return RuleMatch(
                rule_id=None,
                name="默认售后高风险规则",
                action="handoff",
                reason=f"售后高风险：{default_match}",
                target_group="after_sales",
                matched_keyword=default_match,
            )
        return None

    @staticmethod
    def _match_keywords(text: str, keywords: list[str], match_type: str) -> str:
        if match_type == "exact":
            text_key = normalize(text)
            return next((item for item in keywords if normalize(item) == text_key), "")
        if match_type == "regex":
            for item in keywords:
                try:
                    if re.search(item, text, flags=re.IGNORECASE):
                        return item
                except re.error:
                    continue
            return ""
        return next((item for item in keywords if str(item) and str(item) in text), "")
