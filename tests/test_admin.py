from __future__ import annotations

import json

import pytest

from ai_store_support.admin import AdminService
from ai_store_support.config_models import KnowledgeEntry, ShopSettings
from ai_store_support.conversation_models import Conversation, ConversationMessage, HandoffRequest
from ai_store_support.db import create_database
from ai_store_support.models import PhoneModelSupport, UnknownPhoneModelQuery


def make_admin(tmp_path):
    engine, sessions = create_database(tmp_path / "admin.db")
    return AdminService(sessions, engine), sessions


def seed(sessions):
    with sessions() as session:
        session.add_all(
            [
                PhoneModelSupport(
                    shop_key="demo", material_name="磨砂", brand="VIVO",
                    model_name="Y100", normalized_model="Y100", supported=True,
                    stock_status="有货", source_file="seed.xlsx",
                ),
                PhoneModelSupport(
                    shop_key="demo", material_name="液态", brand="VIVO",
                    model_name="Y100", normalized_model="Y100", supported=False,
                    stock_status="待到货", source_file="seed.xlsx",
                ),
                UnknownPhoneModelQuery(
                    shop_key="demo", brand="VIVO", model_name="Y999",
                    normalized_model="Y999", raw_query="y999有吗", query_count=3,
                ),
                KnowledgeEntry(
                    shop_key="demo", title="多久发货", content="按商品页承诺时效发出",
                    tags_json=json.dumps(["发货", "物流"], ensure_ascii=False), enabled=True,
                ),
                ShopSettings(shop_key="demo", shop_name="测试店铺"),
            ]
        )
        conversation = Conversation(
            shop_key="demo", channel="pinduoduo", external_conversation_id="u-1",
            customer_id="u-1", status="human", last_intent="after_sales",
        )
        session.add(conversation)
        session.flush()
        session.add(ConversationMessage(conversation_id=conversation.id, role="user", content="发错型号了", source="channel"))
        session.add(HandoffRequest(shop_key="demo", conversation_id=conversation.id, reason="wrong_model", target_group="after_sales"))
        session.commit()


def test_dashboard_and_lists(tmp_path):
    admin, sessions = make_admin(tmp_path)
    seed(sessions)

    dashboard = admin.dashboard("demo")
    assert dashboard["models"] == 2
    assert dashboard["supported_models"] == 1
    assert dashboard["unknown_pending"] == 1
    assert dashboard["unknown_queries"] == 3
    assert dashboard["knowledge_enabled"] == 1
    assert dashboard["conversations_human"] == 1
    assert dashboard["handoffs_pending"] == 1

    models = admin.list_phone_models("demo", query="Y100")
    assert len(models) == 2
    assert {row["material_name"] for row in models} == {"磨砂", "液态"}

    unknown = admin.list_unknown_models("demo")
    assert unknown[0]["model_name"] == "Y999"
    assert unknown[0]["query_count"] == 3


def test_promote_unknown_and_edit_model(tmp_path):
    admin, sessions = make_admin(tmp_path)
    seed(sessions)
    row_id = admin.list_unknown_models("demo")[0]["id"]

    created_id = admin.promote_unknown_model(row_id, material_name="磨砂", stock_status="已确认")
    created = [row for row in admin.list_phone_models("demo", query="Y999") if row["id"] == created_id][0]
    assert created["supported"] is True
    assert created["stock_status"] == "已确认"
    assert admin.list_unknown_models("demo", status="resolved")[0]["id"] == row_id

    admin.update_phone_model(created_id, supported=False, stock_status="缺货")
    changed = admin.list_phone_models("demo", query="Y999")[0]
    assert changed["supported"] is False
    assert changed["stock_status"] == "缺货"


def test_knowledge_settings_and_channel_account_guard(tmp_path):
    admin, sessions = make_admin(tmp_path)
    seed(sessions)

    knowledge_id = admin.save_knowledge(
        "demo", title="材质区别", content="磨砂偏硬，液态更柔软",
        tags=["材质", "手感"], priority=8, direct_reply=True,
    )
    rows = admin.list_knowledge("demo", query="材质")
    assert any(row["id"] == knowledge_id and row["priority"] == 8 for row in rows)

    settings = admin.update_settings("demo", ai_enabled=True, max_history_messages=20)
    assert settings["ai_enabled"] is True
    assert settings["max_history_messages"] == 20

    account_id = admin.save_channel_account(
        "demo", channel="pinduoduo", account_key="cs-1", display_name="售前1号",
        transport_name="authorized-local-bridge", settings={"region": "cn", "group": "sales"},
    )
    assert admin.list_channel_accounts("demo")[0]["id"] == account_id

    with pytest.raises(ValueError, match="不能保存凭据"):
        admin.save_channel_account(
            "demo", channel="pinduoduo", account_key="cs-2",
            settings={"access_token": "should-not-be-persisted"},
        )


def test_conversation_and_handoff_controls(tmp_path):
    admin, sessions = make_admin(tmp_path)
    seed(sessions)

    conversation = admin.list_conversations("demo", status="human")[0]
    messages = admin.conversation_messages(conversation["id"])
    assert messages[0]["content"] == "发错型号了"

    handoff = admin.list_handoffs("demo")[0]
    admin.resolve_handoff(handoff["id"], status="resolved", conversation_status="ai")
    assert admin.list_handoffs("demo", status="resolved")[0]["id"] == handoff["id"]
    assert admin.list_conversations("demo", status="ai")[0]["id"] == conversation["id"]
