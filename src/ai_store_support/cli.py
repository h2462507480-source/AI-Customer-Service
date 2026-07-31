from __future__ import annotations

import argparse
import json

from .db import create_database
from .factory import create_orchestrator
from .handoff import HandoffService
from .knowledge import KnowledgeService
from .rules import RuleService
from .schemas import InboundMessage
from .service import PhoneModelService
from .settings import ShopSettingsService


def _json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description="电商AI客服核心服务")
    parser.add_argument("--db", default="data/ai-customer-service.db")
    sub = parser.add_subparsers(dest="command", required=True)

    import_cmd = sub.add_parser("import-models", aliases=["import"])
    import_cmd.add_argument("--shop", required=True)
    import_cmd.add_argument("file")

    query_cmd = sub.add_parser("query-model", aliases=["query"])
    query_cmd.add_argument("--shop", required=True)
    query_cmd.add_argument("message")

    knowledge_add = sub.add_parser("knowledge-add")
    knowledge_add.add_argument("--shop", required=True)
    knowledge_add.add_argument("--title", required=True)
    knowledge_add.add_argument("--content", required=True)
    knowledge_add.add_argument("--tags", default="")
    knowledge_add.add_argument("--priority", type=int, default=0)
    knowledge_add.add_argument("--ai-grounding-only", action="store_true")

    knowledge_import = sub.add_parser("knowledge-import")
    knowledge_import.add_argument("--shop", required=True)
    knowledge_import.add_argument("file")

    rule_add = sub.add_parser("rule-add")
    rule_add.add_argument("--shop", required=True)
    rule_add.add_argument("--name", required=True)
    rule_add.add_argument("--keywords", required=True, help="多个关键词用逗号分隔")
    rule_add.add_argument("--action", choices=["handoff", "fixed_reply", "ignore"], required=True)
    rule_add.add_argument("--reply", default="")
    rule_add.add_argument("--reason", default="")
    rule_add.add_argument("--target-group", default="")
    rule_add.add_argument("--priority", type=int, default=0)

    settings_cmd = sub.add_parser("shop-settings")
    settings_cmd.add_argument("--shop", required=True)
    settings_cmd.add_argument("--shop-name")
    settings_cmd.add_argument("--ai-enabled", choices=["true", "false"])
    settings_cmd.add_argument("--auto-reply", choices=["true", "false"])

    reply_cmd = sub.add_parser("reply")
    reply_cmd.add_argument("--shop", required=True)
    reply_cmd.add_argument("--conversation", required=True)
    reply_cmd.add_argument("--customer", default="local-customer")
    reply_cmd.add_argument("--channel", default="local")
    reply_cmd.add_argument("message")

    handoff_cmd = sub.add_parser("pending-handoffs")
    handoff_cmd.add_argument("--shop")

    args = parser.parse_args()
    engine, session_factory = create_database(args.db)

    if args.command in {"import-models", "import"}:
        _json(PhoneModelService(session_factory, engine).import_file(args.shop, args.file))
        return
    if args.command in {"query-model", "query"}:
        service = PhoneModelService(session_factory, engine)
        result = service.query_text(args.shop, args.message)
        _json(result)
        print(service.format_customer_reply(result))
        return
    if args.command == "knowledge-add":
        tags = [item.strip() for item in args.tags.replace("，", ",").split(",") if item.strip()]
        entry_id = KnowledgeService(session_factory).upsert(
            shop_key=args.shop,
            title=args.title,
            content=args.content,
            tags=tags,
            priority=args.priority,
            direct_reply=not args.ai_grounding_only,
        )
        _json({"knowledge_entry_id": entry_id})
        return
    if args.command == "knowledge-import":
        _json(KnowledgeService(session_factory).import_file(args.shop, args.file))
        return
    if args.command == "rule-add":
        keywords = [item.strip() for item in args.keywords.replace("，", ",").split(",") if item.strip()]
        rule_id = RuleService(session_factory).upsert(
            shop_key=args.shop,
            name=args.name,
            keywords=keywords,
            action=args.action,
            reply_text=args.reply,
            reason=args.reason,
            target_group=args.target_group,
            priority=args.priority,
        )
        _json({"routing_rule_id": rule_id})
        return
    if args.command == "shop-settings":
        values = {}
        if args.shop_name is not None:
            values["shop_name"] = args.shop_name
        if args.ai_enabled is not None:
            values["ai_enabled"] = args.ai_enabled == "true"
        if args.auto_reply is not None:
            values["auto_reply_enabled"] = args.auto_reply == "true"
        row = ShopSettingsService(session_factory).update(args.shop, **values)
        _json(
            {
                "shop_key": row.shop_key,
                "shop_name": row.shop_name,
                "ai_enabled": row.ai_enabled,
                "auto_reply_enabled": row.auto_reply_enabled,
            }
        )
        return
    if args.command == "reply":
        orchestrator = create_orchestrator(args.db)
        decision = orchestrator.process(
            InboundMessage(
                shop_key=args.shop,
                conversation_id=args.conversation,
                customer_id=args.customer,
                content=args.message,
                channel=args.channel,
            )
        )
        _json(decision.__dict__)
        return
    if args.command == "pending-handoffs":
        _json(HandoffService(session_factory).list_pending(args.shop))
        return


if __name__ == "__main__":
    main()
