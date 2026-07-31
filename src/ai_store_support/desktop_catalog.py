from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from .desktop_common import BaseTab, TableFrame


class ModelsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.query_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.query_var, width=28).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="搜索", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="导入型号表", command=self.import_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="修改库存", command=self.edit_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="删除", command=self.delete_selected).pack(side=tk.LEFT, padx=5)
        self.table = TableFrame(self, [
            ("id", "ID", 60), ("brand", "品牌", 90), ("model", "型号", 150),
            ("material", "材质", 180), ("supported", "可售", 70),
            ("stock", "库存状态", 120), ("source", "来源", 180), ("updated", "更新时间", 150),
        ])
        self.table.pack(fill=tk.BOTH, expand=True)
        self.table.tree.bind("<Double-1>", lambda _event: self.edit_selected())

    def refresh(self) -> None:
        rows = self.admin.list_phone_models(self.shop, query=self.query_var.get(), limit=2000)
        display = [{**row, "model": row["model_name"], "material": row["material_name"], "supported": "是" if row["supported"] else "否", "stock": row["stock_status"], "source": row["source_file"], "updated": row["updated_at"]} for row in rows]
        self.table.set_rows(display, ["id", "brand", "model", "material", "supported", "stock", "source", "updated"])

    def import_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="选择型号表", filetypes=[("型号表", "*.xlsx *.xlsm *.csv"), ("所有文件", "*.*")])
        if path:
            self.app.run_background("正在导入型号表…", lambda: self.admin.import_models(self.shop, path), lambda result: messagebox.showinfo("导入完成", json.dumps(result, ensure_ascii=False, indent=2), parent=self))

    def edit_selected(self) -> None:
        row = self.require_row(self.table)
        if not row:
            return
        available = messagebox.askyesnocancel("修改库存", "该型号当前是否可售？\n选择“是”为可售，“否”为不可售。", parent=self)
        if available is None:
            return
        stock = simpledialog.askstring("库存状态", "请输入库存状态：", initialvalue=row.get("stock_status", ""), parent=self)
        if stock is not None:
            self.admin.update_phone_model(row["id"], supported=available, stock_status=stock)
            self.refresh()

    def delete_selected(self) -> None:
        row = self.require_row(self.table)
        if row and messagebox.askyesno("确认删除", f"确定删除 {row['brand']} {row['model_name']} / {row['material_name']}？", parent=self):
            self.admin.delete_phone_model(row["id"])
            self.refresh()


class UnknownTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.status_var = tk.StringVar(value="pending")
        ttk.Combobox(toolbar, textvariable=self.status_var, values=["pending", "resolved", "ignored", "all"], state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="加入型号库", command=self.promote).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="标记忽略", command=lambda: self.set_status("ignored")).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="重新待处理", command=lambda: self.set_status("pending")).pack(side=tk.LEFT, padx=5)
        self.table = TableFrame(self, [
            ("id", "ID", 60), ("brand", "品牌", 90), ("model", "型号", 130),
            ("query", "买家原话", 360), ("count", "次数", 70), ("status", "状态", 90), ("last", "最近咨询", 160),
        ])
        self.table.pack(fill=tk.BOTH, expand=True)

    def refresh(self) -> None:
        rows = self.admin.list_unknown_models(self.shop, status=self.status_var.get())
        display = [{**row, "model": row["model_name"], "query": row["raw_query"], "count": row["query_count"], "last": row["last_seen_at"]} for row in rows]
        self.table.set_rows(display, ["id", "brand", "model", "query", "count", "status", "last"])

    def set_status(self, status: str) -> None:
        row = self.require_row(self.table)
        if row:
            self.admin.set_unknown_status(row["id"], status)
            self.refresh()

    def promote(self) -> None:
        row = self.require_row(self.table)
        if not row:
            return
        material = simpledialog.askstring("加入型号库", "请输入确认支持的材质名称：", parent=self)
        if not material:
            return
        available = messagebox.askyesno("库存状态", "该型号当前是否可售？", parent=self)
        stock = simpledialog.askstring("库存状态", "请输入库存备注：", initialvalue="有货" if available else "待到货", parent=self)
        if stock is not None:
            self.admin.promote_unknown_model(row["id"], material_name=material, supported=available, stock_status=stock)
            self.refresh()


class KnowledgeTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.query_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.query_var, width=28).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="搜索", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="导入知识库", command=self.import_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="新增", command=self.add).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="编辑", command=self.edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="删除", command=self.delete).pack(side=tk.LEFT, padx=5)
        self.table = TableFrame(self, [
            ("id", "ID", 60), ("title", "标题", 230), ("content", "内容", 430),
            ("tags", "标签", 180), ("priority", "优先级", 75), ("enabled", "启用", 65), ("direct", "直接回复", 80),
        ])
        self.table.pack(fill=tk.BOTH, expand=True)
        self.table.tree.bind("<Double-1>", lambda _event: self.edit())

    def refresh(self) -> None:
        rows = self.admin.list_knowledge(self.shop, query=self.query_var.get())
        display = [{**row, "tags": "、".join(row["tags"]), "enabled": "是" if row["enabled"] else "否", "direct": "是" if row["direct_reply"] else "否"} for row in rows]
        self.table.set_rows(display, ["id", "title", "content", "tags", "priority", "enabled", "direct"])

    def import_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="选择知识库", filetypes=[("知识库", "*.xlsx *.xlsm *.csv"), ("所有文件", "*.*")])
        if path:
            self.app.run_background("正在导入知识库…", lambda: self.admin.import_knowledge(self.shop, path), lambda result: messagebox.showinfo("导入完成", json.dumps(result, ensure_ascii=False, indent=2), parent=self))

    def add(self) -> None:
        self._edit_dialog(None)

    def edit(self) -> None:
        row = self.require_row(self.table)
        if row:
            self._edit_dialog(row)

    def _edit_dialog(self, row: dict[str, Any] | None) -> None:
        title = simpledialog.askstring("知识标题", "标题/常见问题：", initialvalue=row.get("title", "") if row else "", parent=self)
        if not title:
            return
        content = simpledialog.askstring("回复内容", "标准回复内容：", initialvalue=row.get("content", "") if row else "", parent=self)
        if not content:
            return
        initial = "、".join(row.get("tags", [])) if row and isinstance(row.get("tags"), list) else str(row.get("tags", "") if row else "")
        tags_text = simpledialog.askstring("标签", "标签，用逗号分隔：", initialvalue=initial, parent=self) or ""
        priority = simpledialog.askinteger("优先级", "优先级，数值越大越靠前：", initialvalue=int(row.get("priority", 0)) if row else 0, parent=self)
        if priority is None:
            return
        enabled = messagebox.askyesno("是否启用", "启用这条知识吗？", parent=self)
        direct = messagebox.askyesno("直接回复", "命中时是否直接使用这条内容回复？", parent=self)
        tags = [item.strip() for item in tags_text.replace("、", ",").replace("，", ",").split(",") if item.strip()]
        self.admin.save_knowledge(self.shop, title=title, content=content, tags=tags, priority=priority, enabled=enabled, direct_reply=direct, row_id=row.get("id") if row else None)
        self.refresh()

    def delete(self) -> None:
        row = self.require_row(self.table)
        if row and messagebox.askyesno("确认删除", f"确定删除知识“{row['title']}”？", parent=self):
            self.admin.delete_knowledge(row["id"])
            self.refresh()


class RulesTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="新增", command=self.add).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="编辑", command=self.edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="删除", command=self.delete).pack(side=tk.LEFT, padx=5)
        self.table = TableFrame(self, [
            ("id", "ID", 60), ("name", "规则", 170), ("keywords", "关键词", 360),
            ("action", "动作", 90), ("reason", "原因", 150), ("group", "人工组", 110), ("priority", "优先级", 75), ("enabled", "启用", 65),
        ])
        self.table.pack(fill=tk.BOTH, expand=True)

    def refresh(self) -> None:
        rows = self.admin.list_rules(self.shop)
        display = [{**row, "keywords": "、".join(row["keywords"]), "group": row["target_group"], "enabled": "是" if row["enabled"] else "否"} for row in rows]
        self.table.set_rows(display, ["id", "name", "keywords", "action", "reason", "group", "priority", "enabled"])

    def add(self) -> None:
        self._edit(None)

    def edit(self) -> None:
        row = self.require_row(self.table)
        if row:
            self._edit(row)

    def _edit(self, row: dict[str, Any] | None) -> None:
        name = simpledialog.askstring("规则名称", "规匙名称：", initialvalue=row.get("name", "") if row else "", parent=self)
        if not name:
            return
        initial = "、".join(row.get("keywords", [])) if row and isinstance(row.get("keywords"), list) else str(row.get("keywords", "") if row else "")
        keywords_text = simpledialog.askstring("关键词", "关键词，用逗号分隔：", initialvalue=initial, parent=self)
        if not keywords_text:
            return
        action = simpledialog.askstring("动作", "动作：reply / handoff / ignore", initialvalue=row.get("action", "handoff") if row else "handoff", parent=self)
        if action not in {"reply", "handoff", "ignore"}:
            messagebox.showerror("动作错误", "动作必须是 reply、handoff 或 ignore。", parent=self)
            return
        reply = simpledialog.askstring("固定回复", "reply动作的回复内容：", initialvalue=row.get("reply_text", "") if row else "", parent=self) or ""
        reason = simpledialog.askstring("原因", "转人工原因标识：", initialvalue=row.get("reason", "") if row else "", parent=self) or ""
        group = simpledialog.askstring("人工组", "目标人工组：", initialvalue=row.get("target_group", "") if row else "", parent=self) or ""
        priority = simpledialog.askinteger("优先级", "优先级：", initialvalue=int(row.get("priority", 0)) if row else 0, parent=self)
        if priority is None:
            return
        enabled = messagebox.askyesno("启用", "启用这条规则吗？", parent=self)
        keywords = [item.strip() for item in keywords_text.replace("、", ",").replace("，", ",").split(",") if item.strip()]
        self.admin.save_rule(self.shop, name=name, keywords=keywords, action=action, reply_text=reply, reason=reason, target_group=group, priority=priority, enabled=enabled, row_id=row.get("id") if row else None)
        self.refresh()

    def delete(self) -> None:
        row = self.require_row(self.table)
        if row and messagebox.askyesno("确认删除", f"确定删除规匙“{row['name']}”？", parent=self):
            self.admin.delete_rule(row["id"])
            self.refresh()
