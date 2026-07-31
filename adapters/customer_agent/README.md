# Customer-Agent 适配层

该目录用于逐步迁移拼多多登录、WebSocket消息收发、商品卡片和转人工能力。

适配原则：

- 保留底层渠道连接能力
- 使用 `ai_store_support.PhoneModelService` 替代模糊文本型号查询
- 型号查询处理器必须位于通用 AI 回复处理器之前
- 未知型号不得由 AI 猜测
