from __future__ import annotations

from typing import Any

from .ai import AIProvider, DEFAULT_SYSTEM_PROMPT, DisabledAIProvider
from .conversations import ConversationService
from .handoff import HandoffService
from .intents import looks_like_phone_model_query
from .knowledge import KnowledgeService
from .rules import RuleService
from .schemas import InboundMessage, RuleMatch, SupportDecision
from .service import PhoneModelService
from .settings import ShopSettingsService


class CustomerServiceOrchestrator:
    """统一客服决策链：人工状态 -> 规则 -> 型号 -> 知识 -> AI -> 转人工。"""

    def __init__(
        self,
        *,
        phone_models: PhoneModelService,
        conversations: ConversationService,
        handoffs: HandoffService,
        knowledge: KnowledgeService,
        rules: RuleService,
        shop_settings: ShopSettingsService,
        ai_provider: AIProvider | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        direct_knowledge_score: float = 8.0,
    ):
        self.phone_models = phone_models
        self.conversations = conversations
        self.handoffs = handoffs
        self.knowledge = knowledge
        self.rules = rules
        self.shop_settings = shop_settings
        self.ai_provider = ai_provider or DisabledAIProvider()
        self.system_prompt = system_prompt
        self.direct_knowledge_score = direct_knowledge_score

    def process(self, message: InboundMessage) -> SupportDecision:
        content = str(message.content or "").strip()
        if not content:
            return SupportDecision(action="ignore", intent="empty", source="validation")
        settings = self.shop_settings.get(message.shop_key)
        if not settings.auto_reply_enabled:
            return SupportDecision(action="ignore", intent="disabled", source="shop_settings")

        conversation_id = self.conversations.get_or_create(message)
        if self.conversations.get_status(conversation_id) == "human":
            return SupportDecision(
                action="ignore",
                intent="human_takeover",
                source="conversation_state",
                metadata={"conversation_db_id": conversation_id},
            )
        self.conversations.append(conversation_id, "user", content, "channel")

        rule = self.rules.match(message.shop_key, content)
        if rule:
            return self._apply_rule(message, conversation_id, settings.handoff_reply, rule)

        if looks_like_phone_model_query(content):
            model_result = self.phone_models.query_text(message.shop_key, content)
            if model_result["status"] in {"matched", "ambiguous"}:
                reply = self.phone_models.format_customer_reply(model_result)
                return self._reply(
                    conversation_id,
                    reply,
                    intent="phone_model",
                    source="phone_model",
                    metadata={"model_result": model_result},
                )
            return self._handoff(
                message,
                conversation_id,
                reply=settings.handoff_reply,
                reason="未知手机型号",
                target_group="sales",
                intent="phone_model_unknown",
                metadata={"model_result": model_result},
            )

        knowledge = self.knowledge.search(message.shop_key, content)
        if knowledge and knowledge[0].direct_reply and knowledge[0].score >= self.direct_knowledge_score:
            return self._reply(
                conversation_id,
                knowledge[0].content,
                intent="knowledge",
                source="knowledge",
                metadata={"knowledge_entry_id": knowledge[0].entry_id, "score": knowledge[0].score},
            )

        if settings.ai_enabled and self.ai_provider.available:
            history = self.conversations.recent_history(
                conversation_id, limit=settings.max_history_messages
            )
            try:
                reply = self.ai_provider.generate(
                    system_prompt=self.system_prompt,
                    history=history,
                    knowledge=knowledge,
                    context={
                        "shop_key": message.shop_key,
                        "shop_name": settings.shop_name,
                        "channel": message.channel,
                    },
                )
            except RuntimeError as exc:
                return self._handoff(
                    message,
                    conversation_id,
                    reply=settings.fallback_reply,
                    reason="AI服务不可用",
                    target_group="sales",
                    intent="ai_error",
                    metadata={"error": str(exc)},
                )
            return self._reply(
                conversation_id,
                reply,
                intent="ai_answer",
                source="ai",
                metadata={"knowledge_count": len(knowledge)},
            )

        return self._handoff(
            message,
            conversation_id,
            reply=settings.fallback_reply,
            reason="知识库未覆盖",
            target_group="sales",
            intent="fallback",
        )

    def _apply_rule(
        self,
        message: InboundMessage,
        conversation_id: int,
        default_handoff_reply: str,
        rule: RuleMatch,
    ) -> SupportDecision:
        if rule.action == "ignore":
            self.conversations.set_status(conversation_id, "ai", intent="rule_ignore")
            return SupportDecision(
                action="ignore",
                intent="rule_ignore",
                source="rule",
                metadata={"rule_name": rule.name, "matched_keyword": rule.matched_keyword},
            )
        if rule.action == "fixed_reply":
            return self._reply(
                conversation_id,
                rule.reply_text or "亲，收到您的消息。",
                intent="rule_fixed_reply",
                source="rule",
                metadata={"rule_name": rule.name, "matched_keyword": rule.matched_keyword},
            )
        return self._handoff(
            message,
            conversation_id,
            reply=rule.reply_text or default_handoff_reply,
            reason=rule.reason or rule.name,
            target_group=rule.target_group or "after_sales",
            intent="handoff_rule",
            metadata={"rule_name": rule.name, "matched_keyword": rule.matched_keyword},
        )

    def _reply(
        self,
        conversation_id: int,
        reply: str,
        *,
        intent: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> SupportDecision:
        self.conversations.append(conversation_id, "assistant", reply, source)
        self.conversations.set_status(conversation_id, "ai", intent=intent)
        return SupportDecision(
            action="reply",
            reply_text=reply,
            intent=intent,
            source=source,
            metadata={"conversation_db_id": conversation_id, **(metadata or {})},
        )

    def _handoff(
        self,
        message: InboundMessage,
        conversation_id: int,
        *,
        reply: str,
        reason: str,
        target_group: str,
        intent: str,
        metadata: dict[str, Any] | None = None,
    ) -> SupportDecision:
        handoff_id = self.handoffs.create(
            shop_key=message.shop_key,
            conversation_id=conversation_id,
            reason=reason,
            target_group=target_group,
            payload={
                "channel": message.channel,
                "external_conversation_id": message.conversation_id,
                "customer_id": message.customer_id,
                **message.metadata,
                **(metadata or {}),
            },
        )
        self.conversations.append(conversation_id, "assistant", reply, "handoff")
        self.conversations.set_status(conversation_id, "human", intent=intent)
        return SupportDecision(
            action="handoff",
            reply_text=reply,
            intent=intent,
            source="handoff",
            handoff_reason=reason,
            target_group=target_group,
            metadata={
                "conversation_db_id": conversation_id,
                "handoff_request_id": handoff_id,
                **(metadata or {}),
            },
        )
