from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .desktop_common import BaseTab, TableFrame


class OverviewTab(BaseTab):
    METRICS = [
        ("models", "型号记录"), ("supported_models", "可售型号"),
        ("unknown_pending", "待确认型号"), ("unknown_queries", "未知咨询次数"),
        ("knowledge_enabled", "启用知识"), ("conversations_ai", "AI会话"),
        ("conversations_human", "人工会话"), ("handoffs_pending", "待转人工"),
        ("channel_accounts", "启用账号"),
    ]

    def __init__(self, master, app):
        super().__init__(master, app)
        self.labels = {}
        grid = ttk.Frame(self)
        grid.pack(fill=tk.X)
        for index, (key, title) in enumerate(self.METRICS):
            card = ttk.LabelFrame(grid, text=title, padding=18)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)
            label = ttk.Label(card, text="0", font=("Microsoft YaHei UI", 22, "bold"))
            label.pack()
            self.labels[key] = label
        for column in range(3):
            grid.columnconfigure(column, weight=1)
        ttk.Label(self, text="建议优先处理：待确认型号、待转人工会话及处于人工接管状态的会话。", padding=(8, 18)).pack(anchor=tk.W)

    def refresh(self) -> None:
        values = self.admin.dashboard(self.shop)
        for key, label in self.labels.items():
            label.configure(text=str(values.get(key, 0)))


class ConversationsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.status_var = tk.StringVar(value="all")
        ttk.Combobox(toolbar, textvariable=self.status_var, values=["all", "ai", "human", "closed"], state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="交给AI", command=lambda: self.set_status("ai")).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="人工接管", command=lambda: self.set_status("human")).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="关闭会话", command=lambda: self.set_status("closed")).pack(side=tk.LEFT, padx=5)
        pane = ttk.Panedwindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        self.table = TableFrame(pane, [
            ("id", "ID", 60), ("channel", "渠道", 100), ("external", "会话标识", 240),
            ("status", "状态", 80), ("intent", "最近意图", 130), ("count", "消息数", 70), ("updated", "更新时间", 160),
        ])
        pane.add(self.table, weight=3)
        detail = ttk.Frame(pane)
        self.messages = tk.Text(detail, height=12, wrap=tk.WORD, state=tk.DISABLED)
        self.messages.pack(fill=tk.BOTH, expand=True)
        pane.add(detail, weight=2)
        self.table.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_messages())

    def refresh(self) -> None:
        rows = self.admin.list_conversations(self.shop, status=self.status_var.get())
        display = [{**row, "external": row["external_conversation_id"], "intent": row["last_intent"], "count": row["message_count"], "updated": row["updated_at"]} for row in rows]
        self.table.set_rows(display, ["id", "channel", "external", "status", "intent", "count", "updated"])
        self.show_messages()

    def show_messages(self) -> None:
        row = self.table.selected()
        lines = []
        if row:
            for message in self.admin.conversation_messages(row["id"]):
                role = "买家" if message["role"] == "user" else "客服"
                lines.append(f"[{message['created_at']}] {role}（{message['source']}）\n{message['content']}\n")
        self.messages.configure(state=tk.NORMAL)
        self.messages.delete("1.0", tk.END)
        self.messages.insert(tk.END, "\n".join(lines))
        self.messages.configure(state=tk.DISABLED)

    def set_status(self, status: str) -> None:
        row = self.require_row(self.table)
        if row:
            self.admin.set_conversation_status(row["id"], status)
            self.refresh()


class HandoffsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.status_var = tk.StringVar(value="pending")
        ttk.Combobox(toolbar, textvariable=self.status_var, values=["pending", "resolved", "cancelled", "failed", "all"], state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="已转人工", command=lambda: self.resolve("resolved", "human")).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="取消并恢复AI", command=lambda: self.resolve("cancelled", "ai")).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="标记失败", command=lambda: self.resolve("failed", "human")).pack(side=tk.LEFT, padx=5)
        self.table = TableFrame(self, [
            ("id", "ID", 60), ("conversation", "会话ID", 80), ("reason", "原因", 180),
            ("group", "目标组", 120), ("status", "状态", 90), ("created", "创建时间", 160), ("resolved", "处理时间", 160),
        ])
        self.table.pack(fill=tk.BOTH, expand=True)

    def refresh(self) -> None:
        rows = self.admin.list_handoffs(self.shop, status=self.status_var.get())
        display = [{**row, "conversation": row["conversation_id"], "group": row["target_group"], "created": row["created_at"], "resolved": row["resolved_at"]} for row in rows]
        self.table.set_rows(display, ["id", "conversation", "reason", "group", "status", "created", "resolved"])

    def resolve(self, status: str, conversation_status: str) -> None:
        row = self.require_row(self.table)
        if row:
            self.admin.resolve_handoff(row["id"], status=status, conversation_status=conversation_status)
            self.refresh()


class SettingsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        form = ttk.LabelFrame(self, text="店铺设置", padding=16)
        form.pack(fill=tk.X, anchor=tk.N)
        self.vars = {
            "shop_name": tk.StringVar(), "auto_reply_enabled": tk.BooleanVar(),
            "ai_enabled": tk.BooleanVar(), "max_history_messages": tk.IntVar(value=12),
            "handoff_reply": tk.StringVar(), "fallback_reply": tk.StringVar(),
        }
        fields = [("店铺名称", "shop_name"), ("最大历史消息数", "max_history_messages"), ("转人工提示", "handoff_reply"), ("兜底提示", "fallback_reply")]
        for row, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=6)
            ttk.Entry(form, textvariable=self.vars[key], width=90).grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        ttk.Checkbutton(form, text="启用自动回复", variable=self.vars["auto_reply_enabled"]).grid(row=4, column=1, sticky=tk.W, padx=8, pady=6)
        ttk.Checkbutton(form, text="启用AI回复", variable=self.vars["ai_enabled"]).grid(row=5, column=1, sticky=tk.W, padx=8, pady=6)
        ttk.Button(form, text="保存设置", command=self.save).grid(row=6, column=1, sticky=tk.W, padx=8, pady=12)
        form.columnconfigure(1, weight=1)
        ttk.Label(self, text="AI接口密钥仍通过操作系统环境变量注入，不会在此界面或数据库中保存。", padding=(4, 16)).pack(anchor=tk.W)

    def refresh(self) -> None:
        values = self.admin.get_settings(self.shop)
        for key, variable in self.vars.items():
            variable.set(values.get(key))

    def save(self) -> None:
        self.admin.update_settings(self.shop, **{key: variable.get() for key, variable in self.vars.items()})
        messagebox.showinfo("保存成功", "店铺设置已保存。", parent=self)
        self.refresh()


class ChannelsTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(toolbar, text="新增账号元数据", command=self.add).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="删除", command=self.delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="刷新状态", command=self.refresh).pack(side=tk.LEFT, padx=5)
        pane = ttk.Panedwindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        self.accounts = TableFrame(pane, [
            ("id", "ID", 60), ("channel", "渠道", 110), ("account", "账号标识", 180),
            ("name", "显示名称", 150), ("transport", "传输实现", 220), ("enabled", "启用", 70), ("updated", "更新时间", 160),
        ])
        pane.add(self.accounts, weight=2)
        self.statuses = TableFrame(pane, [
            ("runtime", "运行标识", 220), ("state", "状态", 100), ("received", "接收", 70),
            ("sent", "发送", 70), ("handoffs", "转人工", 80), ("last", "最近事件", 160), ("error", "错误", 300),
        ])
        pane.add(self.statuses, weight=2)

    def refresh(self) -> None:
        rows = self.admin.list_channel_accounts(self.shop)
        display = [{**row, "account": row["account_key"], "name": row["display_name"], "transport": row["transport_name"], "enabled": "是" if row["enabled"] else "否", "updated": row["updated_at"]} for row in rows]
        self.accounts.set_rows(display, ["id", "channel", "account", "name", "transport", "enabled", "updated"])
        statuses = self.app.registry.list(shop_key=self.shop)
        state_rows = [{**row, "id": row["runtime_key"], "runtime": row["runtime_key"], "received": row["received_messages"], "sent": row["sent_messages"], "last": row["last_event_at"], "error": row["last_error"]} for row in statuses]
        self.statuses.set_rows(state_rows, ["runtime", "state", "received", "sent", "handoffs", "last", "error"])

    def add(self) -> None:
        channel = simpledialog.askstring("渠道", "渠道名称：", initialvalue="pinduoduo", parent=self)
        if not channel:
            return
        account_key = simpledialog.askstring("账号标识", "非敏感账号标识：", parent=self)
        if not account_key:
            return
        name = simpledialog.askstring("显示名称", "显示名称：", parent=self) or account_key
        transport = simpledialog.askstring("传输实现", "已授权传输实现名称：", initialvalue="authorized-local-bridge", parent=self) or ""
        settings_text = simpledialog.askstring("非敏感设置", "可选JSON设置（禁止Cookie、Token、密码等凭据）：", initialvalue="{}", parent=self) or "{}"
        try:
            settings = json.loads(settings_text)
            if not isinstance(settings, dict):
                raise ValueError("设置必须是JSON对象")
            self.admin.save_channel_account(self.shop, channel=channel, account_key=account_key, display_name=name, transport_name=transport, settings=settings)
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            return
        self.refresh()

    def delete(self) -> None:
        row = self.require_row(self.accounts)
        if row and messagebox.askyesno("确认删除", f"确定删除渠道账号“{row['display_name'] or row['account_key']}”？", parent=self):
            self.admin.delete_channel_account(row["id"])
            self.refresh()
