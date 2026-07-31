# 拼多多 Customer-Agent 适配层

该目录将在下一阶段承载拼多多真实渠道能力：

- 登录与会话保持
- WebSocket 消息接收
- 文本及商品卡片发送
- 真正执行转人工
- 断线重连和账号状态

适配器收到买家消息后，转换成 `InboundMessage` 并交给 `CustomerServiceOrchestrator`。适配器只执行决策结果，不负责判断型号、售后风险或知识答案。

当前核心已经提供：

- `ChannelAdapter.send_text`
- `ChannelAdapter.transfer_to_human`
- `SupportRuntime.handle`

型号查询必须先于 AI；未知型号和售后高风险问题必须转人工，不得让 AI 猜测。
