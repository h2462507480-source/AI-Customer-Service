# AI Store Support

面向电商店铺的智能客服项目。当前第一阶段专注手机壳型号查询：由结构化数据库确定“材质—品牌—型号—库存”关系，AI只负责理解买家表达和组织回复，禁止猜测型号支持情况。

## 当前能力

- 导入 XLSX/CSV 型号表
- 兼容列名：材质、品牌栏目、型号组合、库存状态
- 拆分 `苹果7/8/SE2/SE3` 等通用型号组合
- 精确区分 `Y100/Y100i`、`15/15PRO`
- 按不同材质分别判断支持状态
- 相似型号提示买家确认
- 未知型号自动记录
- 提供 CLI，方便后续接入拼多多消息通道和桌面端

## 快速开始

```bash
python -m pip install -e ".[dev]"
pytest -q

ai-store-support import --shop demo models.xlsx
ai-store-support query --shop demo "vivo y100有吗"
```

## 开发方向

1. 型号管理桌面界面
2. 拼多多消息收发适配器
3. 售前规则与售后转人工
4. 未知型号统计与供应链更新

## 来源说明

项目设计参考了 MIT 许可的 `JC0v0/Customer-Agent` 的消息处理、知识库和转人工思路，但本仓库采用独立结构重新开发，避免继续依赖 Fork 分支。
