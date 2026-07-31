from __future__ import annotations

from pathlib import Path

from .ai import DisabledAIProvider, OpenAICompatibleProvider
from .conversations import ConversationService
from .db import create_database
from .handoff import HandoffService
from .knowledge import KnowledgeService
from .orchestrator import CustomerServiceOrchestrator
from .rules import RuleService
from .service import PhoneModelService
from .settings import AISettings, ShopSettingsService


def create_orchestrator(
    db_path: str | Path,
    *,
    ai_settings: AISettings | None = None,
) -> CustomerServiceOrchestrator:
    engine, session_factory = create_database(db_path)
    resolved_ai = ai_settings or AISettings.from_env()
    provider = OpenAICompatibleProvider(resolved_ai) if resolved_ai.enabled else DisabledAIProvider()
    return CustomerServiceOrchestrator(
        phone_models=PhoneModelService(session_factory, engine),
        conversations=ConversationService(session_factory),
        handoffs=HandoffService(session_factory),
        knowledge=KnowledgeService(session_factory),
        rules=RuleService(session_factory),
        shop_settings=ShopSettingsService(session_factory),
        ai_provider=provider,
    )
