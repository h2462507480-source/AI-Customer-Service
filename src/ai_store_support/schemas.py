from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class InboundMessage:
    shop_key: str
    conversation_id: str
    customer_id: str
    content: str
    channel: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class KnowledgeMatch:
    entry_id: int
    title: str
    content: str
    tags: tuple[str, ...]
    score: float
    direct_reply: bool


@dataclass(frozen=True)
class RuleMatch:
    rule_id: int | None
    name: str
    action: str
    reply_text: str = ""
    reason: str = ""
    target_group: str = ""
    matched_keyword: str = ""


@dataclass(frozen=True)
class SupportDecision:
    action: Literal["reply", "handoff", "ignore"]
    reply_text: str = ""
    intent: str = ""
    source: str = ""
    handoff_reason: str = ""
    target_group: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
