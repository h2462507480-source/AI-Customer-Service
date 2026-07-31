# AI Customer Service

面向电商店铺的 AI 客服项目。当前版本已具备手机壳型号确定性查询、业务规则、知识库、AI 多轮会话、转人工决策、渠道适配边界和 Windows 桌面管理客户端。

## 已实现

- 导入 XLSX/CSV 手机型号表，精确区分相似型号并按材质判断支持状态
- 未知型号记录；退款、投诉、发错货等高风险问题优先转人工
- 固定回复、忽略、转人工规则和已审核客服知识库
- OpenAI 兼容大模型接口与多轮对话记录
- 拼多多消息解析、消息去重、发送回复和转人工适配接口
- 桌面后台：运行中心、业务总览、型号库、未知型号、知识库、规则、会话、转人工、操作日志、店铺设置和渠道账号
- 渠道服务守护：异常退出检测、指数退避、自动重连和最大重启次数保护
- 结构化 JSONL 操作日志：记录收消息、决策来源、回复、转人工、渠道异常和备份，并自动脱敏凭据字段
- SQLite 在线自动备份、手动备份、30 天保留策略和旧备份清理
- PyInstaller Windows 单文件程序、Inno Setup 安装包和 GitHub Actions 构建产物

## 客服处理顺序

1. 人工是否已经接管
2. 售后高风险和固定业务规则
3. 手机型号精确查询
4. 已审核知识直接回复
5. 基于审核知识的 AI 回复
6. 无法确定时转人工

## 开发运行

```bash
python -m pip install -e ".[dev]"
python -m pytest -q

ai-store-support import-models --shop demo models.xlsx
ai-store-support knowledge-add --shop demo --title "多久发货" --content "按商品页承诺时效发出" --tags "发货时间,多久发货"
ai-store-support shop-settings --shop demo --ai-enabled true
ai-store-support reply --shop demo --conversation test-1 "vivo y100有吗"
ai-store-support-launcher
```

## AI 配置

通过环境变量配置 OpenAI 兼容接口：

```text
AI_BASE_URL=https://example.com/v1
AI_API_KEY=your-key
AI_MODEL=your-model
```

API Key 不写入数据库、运行日志或操作日志。

## 客户端数据

Windows 默认写入 `%LOCALAPPDATA%\AI-Customer-Service`：

```text
data\ai-store-support.db
logs\customer-service.log
logs\operations.jsonl
backups\ai-store-support-*.db
```

可通过以下环境变量覆盖：

```text
AI_STORE_HOME
AI_STORE_DB
AI_STORE_LOG_DIR
AI_STORE_OPERATION_LOG
AI_STORE_BACKUP_DIR
AI_STORE_BACKUP_INTERVAL_SECONDS
AI_STORE_BACKUP_RETENTION_DAYS
AI_STORE_BACKUP_MAX_FILES
AI_STORE_BACKUP_ON_STARTUP
```

## Windows 构建

安装 Python 3.11+ 和 NSIS 后执行：

```powershell
.\packaging\build_windows.ps1 -Python python
```

生成目录：

```text
release\AI-Customer-Service.exe
release\AI-Customer-Service-Portable.zip
release\AI-Customer-Service-Setup.exe
release\SHA256SUMS.txt
```

`.github/workflows/windows-build.yml` 会在开发分支和 PR 上运行全部测试，构建单文件程序与安装包，并上传保留 30 天的 Windows 构建产物。

## 当前边界

- 平台连接仍需独立、已授权的传输实现提供登录状态和真实消息通道
- 尚未使用真实拼多多测试店铺完成端到端联调
- 商品卡片、订单和物流查询尚未接入
- 当前 PR 保持草稿状态，未合并到 `main`
