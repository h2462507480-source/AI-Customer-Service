from ai_store_support.pinduoduo.cookies import normalize_cookies
from ai_store_support.pinduoduo.models import PinduoduoAccount
from ai_store_support.pinduoduo.parser import event_to_inbound_message, parse_pinduoduo_event


def customer_text(msg_id: str = "m-1", content: str = "vivo y100有吗") -> dict:
    return {
        "response": "push",
        "message": {
            "msg_id": msg_id, "type": 0, "sub_type": 99, "content": content,
            "from": {"role": "user", "uid": "buyer-1"},
            "to": {"role": "mall_cs", "uid": "cs-1"},
            "nickname": "买家", "time": 123456,
        },
    }


def test_parser_converts_customer_text_and_ignores_mall_cs():
    account = PinduoduoAccount(shop_key="shop-a", shop_id="mall-1", user_id="account-1", cookies={})
    event = parse_pinduoduo_event(customer_text())
    inbound = event_to_inbound_message(event, account)
    assert inbound is not None
    assert inbound.channel == "pinduoduo"
    assert inbound.customer_id == "buyer-1"
    assert inbound.content == "vivo y100有吗"

    outgoing = customer_text()
    outgoing["message"]["from"] = {"role": "mall_cs", "uid": "cs-1"}
    outgoing_event = parse_pinduoduo_event(outgoing)
    assert outgoing_event.is_customer_message is False
    assert event_to_inbound_message(outgoing_event, account) is None


def test_parser_extracts_goods_and_order_metadata():
    goods = customer_text(content="")
    goods["message"]["sub_type"] = 0
    goods["message"]["info"] = {"goodsID": 88, "goodsName": "菲林手机壳"}
    event = parse_pinduoduo_event(goods)
    assert event.kind == "goods_inquiry"
    assert event.metadata["goods_id"] == 88

    order = customer_text(content="")
    order["message"]["sub_type"] = 1
    order["message"]["info"] = {
        "orderSequenceNo": "order-1", "goodsID": 88,
        "goodsName": "菲林手机壳", "spec": "苹果15",
    }
    event = parse_pinduoduo_event(order)
    assert event.kind == "order_info"
    assert event.metadata["order_id"] == "order-1"
    assert event.metadata["spec"] == "苹果15"


def test_cookie_normalization_supports_browser_export_and_mapping():
    assert normalize_cookies([{"name": "session", "value": "test"}]) == {"session": "test"}
    assert normalize_cookies({"cookies": {"user": "u-1"}}) == {"user": "u-1"}
