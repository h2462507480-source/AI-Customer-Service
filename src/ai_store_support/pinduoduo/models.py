from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PinduoduoAccount:
    """拼多多客服账号运行配置。

    cookies 仅存在于当前进程内存中；日志和异常信息不得输出完整 cookie。
    """

    shop_key: str
    shop_id: str
    user_id: str
    cookies: dict[str, str]
    username: str = ""
    current_cs_uid: str = ""
    group_routes: dict[str, str] = field(default_factory=dict)
    api_version: str = "202506091557"

    @property
    def runtime_key(self) -> str:
        return f"{self.shop_key}:{self.user_id}"


@dataclass(frozen=True)
class PinduoduoInboundEvent:
    kind: str
    is_customer_message: bool
    msg_id: str = ""
    from_role: str = ""
    from_uid: str = ""
    to_role: str = ""
    to_uid: str = ""
    nickname: str = ""
    timestamp: int | float | None = None
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PinduoduoConnectionStatus:
    state: str
    attempts: int = 0
    last_error: str = ""
