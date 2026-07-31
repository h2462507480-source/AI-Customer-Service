from pathlib import Path

from openpyxl import Workbook

from ai_store_support.channels import MemoryChannelAdapter, SupportRuntime
from ai_store_support.conversations import ConversationService
from ai_store_support.db import create_database
from ai_store_support.handoff import HandoffService
from ai_store_support.knowledge import KnowledgeService
from ai_store_support.orchestrator import CustomerServiceOrchestrator
from ai_store_support.rules import RuleService
from ai_store_support.schemas import InboundMessage
from ai_store_support.service import PhoneModelService
from ai_store_support.settings import ShopSettingsService


class FakeAI:
    available = True

    def __init__(self):
        self.calls = []

    def generate(self, *, system_prompt, history, knowledge, context=None):
        self.calls.append((history, knowledge, context))
        return "这是AI基于已审核知识生成的回复。"


def make_stack(tmp_path: Path, ai=None):
    engine, sessions = create_database(tmp_path / "support.db")
    settings = ShopSettingsService(sessions)
    bot = CustomerServiceOrchestrator(
        phone_models=PhoneModelService(sessions, engine),
        conversations=ConversationService(sessions),
        handoffs=HandoffService(sessions),
        knowledge=KnowledgeService(sessions),
        rules=RuleService(sessions),
        shop_settings=settings,
        ai_provider=ai,
    )
    return bot, sessions, settings


def msg(text, conversation="conv-1"):
    return InboundMessage(
        shop_key="shop-1",
        conversation_id=conversation,
        customer_id="customer-1",
        content=text,
        channel="pinduoduo",
    )


def import_models(bot, tmp_path):
    path = tmp_path / "models.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["材质", "品牌栏目", "型号组合", "库存状态"])
    ws.append(["FL二合一磨砂二代", "VIVO", "VIVOY100/VIVOY100I", "现货"])
    ws.append(["FL液态直边软壳", "VIVO", "VIVOY100", "待到货"])
    wb.save(path)
    bot.phone_models.import_file("shop-1", path)


def test_after_sales_precedes_ai(tmp_path):
    ai = FakeAI()
    bot, _, settings = make_stack(tmp_path, ai)
    settings.update("shop-1", ai_enabled=True)
    decision = bot.process(msg("发错型号了，我要退款"))
    assert decision.action == "handoff"
    assert decision.target_group == "after_sales"
    assert ai.calls == []


def test_model_query_is_deterministic(tmp_path):
    ai = FakeAI()
    bot, _, settings = make_stack(tmp_path, ai)
    settings.update("shop-1", ai_enabled=True)
    import_models(bot, tmp_path)
    decision = bot.process(msg("vivo y100有吗"))
    assert decision.action == "reply"
    assert decision.source == "phone_model"
    assert "二合一磨砂二代" in decision.reply_text
    assert "液态直边软壳暂时没有" in decision.reply_text
    assert ai.calls == []


def test_unknown_model_handoffs(tmp_path):
    bot, _, _ = make_stack(tmp_path)
    import_models(bot, tmp_path)
    decision = bot.process(msg("vivo y999有吗"))
    assert decision.action == "handoff"
    assert decision.intent == "phone_model_unknown"
    assert decision.target_group == "sales"


def test_direct_knowledge_reply(tmp_path):
    ai = FakeAI()
    bot, sessions, settings = make_stack(tmp_path, ai)
    settings.update("shop-1", ai_enabled=True)
    KnowledgeService(sessions).upsert(
        shop_key="shop-1",
        title="多久发货",
        content="亲，正常按商品页承诺时效发出。",
        tags=["多久发货", "发货时间"],
        direct_reply=True,
    )
    decision = bot.process(msg("多久发货"))
    assert decision.source == "knowledge"
    assert ai.calls == []


def test_ai_history_and_human_takeover(tmp_path):
    ai = FakeAI()
    bot, sessions, settings = make_stack(tmp_path, ai)
    settings.update("shop-1", ai_enabled=True)
    KnowledgeService(sessions).upsert(
        shop_key="shop-1",
        title="液态软壳特点",
        content="液态直边软壳手感柔软。",
        tags=["液态", "软壳"],
        direct_reply=False,
    )
    assert bot.process(msg("液态壳是什么材质")).source == "ai"
    assert bot.process(msg("那手感怎么样")).source == "ai"
    assert [item.role for item in ai.calls[-1][0]][-3:] == ["user", "assistant", "user"]
    handoff = bot.process(msg("我要人工客服"))
    ignored = bot.process(msg("还有人在吗"))
    assert handoff.action == "handoff"
    assert ignored.action == "ignore"
    assert ignored.intent == "human_takeover"


def test_runtime_executes_transfer(tmp_path):
    bot, _, _ = make_stack(tmp_path)
    adapter = MemoryChannelAdapter()
    decision = SupportRuntime(bot, {"pinduoduo": adapter}).handle(msg("投诉并退款"))
    assert decision.action == "handoff"
    assert len(adapter.sent_messages) == 1
    assert adapter.transfers[0]["target_group"] == "after_sales"
