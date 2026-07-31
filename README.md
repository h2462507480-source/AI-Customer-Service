# AI Customer Service

面向电商店铺的智能客服项目。当前已完成手机壳型号确定性查询，以及规则、知识库、AI、多轮会话和转人工的核心决策链。

## 已实现

- 导入 XLSX/CSV 手机型号表
- 精确区分相似型号，并按材质分别判断支持状态
- 未知型号记录并转人工
- 售后高风险关键词优先转人工
- 可配置固定回复、忽略及转人工规则
- XLSX/CSV 客服知识库导入与审核知识检索
- OpenAI 兼容协议的大模型接口
- 多轮会话记录与人工接管状态
- 渠道适配器接口：发送回复、执行转人工
- CLI 管理入口与 GitHub Actions 测试

## 处理顺序

1. 人工是否已接管
2. 售后高风险及固定规则
3. 手机型号精确查询
4. 已审核知识直接回复
5. 基于审核知识的 AI 回复
6. 转人工兜底

## 开发运行

```bash
python -m pip install -e ".[dev]"
pytest -q

ai-store-support import-models --shop demo models.xlsx
ai-store-support knowledge-add --shop demo --title "多久发货" --content "按商品页承诺时效发出" --tags "发货时间,多久发货"
ai-store-support shop-settings --shop demo --ai-enabled true
ai-store-support reply --shop demo --conversation test-1 "vivo y100有吗"
```

## AI 配置

通过环境变量配置 OpenAI 兼容接口：

```text
AI_BASE_URL=https://example.com/v1
AI_API_KEY=your-key
AI_MODEL=your-model
```

API Key 不写入数据库和日志。

## 下一阶段

- 迁移拼多多登录、WebSocket 消息接收和消息发送
- 对接拼多多真实转人工动作
- 桌面管理界面
- Windows 安装包与自动重连
