from __future__ import annotations

import json
from typing import Any

from ..schemas import InboundMessage
from .models import PinduoduoAccount, PinduoduoInboundEvent


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def parse_pinduoduo_event(payload: str | bytes | dict[str, Any]) -> PinduoduoInboundEvent:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload) if isinstance(payload, str) else payload
    if not isinstance(data, dict):
        raise TypeError("invalid pinduoduo message")

    response = _text(data.get("response"))
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    recipient = message.get("to") if isinstance(message.get("to"), dict) else {}
    common = {
        "msg_id": _text(message.get("msg_id")),
        "from_role": _text(sender.get("role")),
        "from_uid": _text(sender.get("uid")),
        "to_role": _text(recipient.get("role")),
        "to_uid": _text(recipient.get("uid")),
        "nickname": _text(message.get("nickname")),
        "timestamp": message.get("time"),
    }
    metadata: dict[str, Any] = {
        "response": response,
        "message_type": message.get("type"),
        "sub_type": message.get("sub_type"),
    }

    if response != "push":
        return PinduoduoInboundEvent(
            kind="auth" if response == "auth" else "system",
            is_customer_message=False,
            content=response,
            metadata=metadata,
        )
    if common["from_role"] == "mall_cs":
        return PinduoduoInboundEvent(
            kind="mall_cs", is_customer_message=False,
            content=_text(message.get("content")), metadata=metadata, **common,
        )

    msg_type = message.get("type")
    sub_type = message.get("sub_type")
    info = message.get("info") if isinstance(message.get("info"), dict) else {}
    content = _text(message.get("content"))
    kind = "unsupported"

    if msg_type == 0 and sub_type == 1:
        kind = "order_info"
        metadata.update({
            "order_id": info.get("orderSequenceNo"),
            "goods_id": info.get("goodsID"),
            "goods_name": info.get("goodsName"),
            "after_sales_status": info.get("afterSalesStatus"),
            "after_sales_type": info.get("afterSalesType"),
            "spec": info.get("spec"),
        })
        content = content or f"咨询订单：{_text(info.get('goodsName')) or '订单信息'}"
    elif msg_type == 0 and sub_type == 0 and info:
        kind = "goods_inquiry"
        metadata.update({
            "goods_id": info.get("goodsID"),
            "goods_name": info.get("goodsName"),
            "goods_price": info.get("goodsPrice"),
            "goods_thumb_url": info.get("goodsThumbUrl"),
            "link_url": info.get("linkUrl"),
        })
        content = content or f"咨询商品：{_text(info.get('goodsName')) or '商品详情'}"
    elif msg_type == 0:
        kind = "text"
    elif msg_type == 1:
        kind, content = "image", "[买家发送了一张图片]"
    elif msg_type == 14:
        kind, content = "video", "[买家发送了一段视频]"
    elif msg_type == 5:
        kind, content = "emotion", "[表情]"
    elif msg_type == 64:
        kind = "goods_spec"
        spec = info.get("data") if isinstance(info.get("data"), dict) else {}
        metadata.update({
            "goods_id": spec.get("goodsID"), "goods_name": spec.get("goodsName"),
            "goods_price": spec.get("goodsPrice"), "spec": spec.get("spec"),
        })
        content = content or f"咨询规格：{_text(spec.get('spec')) or '商品规格'}"
    elif msg_type == 24:
        kind, content = "transfer", "会话转接事件"
    elif msg_type == 1002:
        kind, content = "withdraw", "消息已撤回"

    accepted = {"text", "goods_inquiry", "order_info", "goods_spec", "image", "video", "emotion"}
    return PinduoduoInboundEvent(
        kind=kind, is_customer_message=kind in accepted,
        content=content, metadata=metadata, **common,
    )


def event_to_inbound_message(
    event: PinduoduoInboundEvent,
    account: PinduoduoAccount,
) -> InboundMessage | None:
    if not event.is_customer_message or not event.from_uid:
        return None
    return InboundMessage(
        shop_key=account.shop_key,
        conversation_id=event.from_uid,
        customer_id=event.from_uid,
        content=event.content,
        channel="pinduoduo",
        metadata={
            **event.metadata,
            "msg_id": event.msg_id,
            "nickname": event.nickname,
            "timestamp": event.timestamp,
            "recipient_uid": event.from_uid,
            "pdd_shop_id": account.shop_id,
            "pdd_user_id": account.user_id,
            "current_cs_uid": account.current_cs_uid,
            "pdd_event_kind": event.kind,
        },
    )
