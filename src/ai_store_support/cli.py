from __future__ import annotations

import argparse
import json

from .db import create_database
from .service import PhoneModelService


def main() -> None:
    parser = argparse.ArgumentParser(description="手机壳型号客服核心服务")
    parser.add_argument("--db", default="data/ai-store-support.db")
    sub = parser.add_subparsers(dest="command", required=True)

    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("--shop", required=True)
    import_cmd.add_argument("file")

    query_cmd = sub.add_parser("query")
    query_cmd.add_argument("--shop", required=True)
    query_cmd.add_argument("message")

    args = parser.parse_args()
    engine, session_factory = create_database(args.db)
    service = PhoneModelService(session_factory, engine)

    if args.command == "import":
        print(json.dumps(service.import_file(args.shop, args.file), ensure_ascii=False, indent=2))
    else:
        result = service.query_text(args.shop, args.message)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(service.format_customer_reply(result))


if __name__ == "__main__":
    main()
