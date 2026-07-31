from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

from .desktop_common import BaseTab, TableFrame


def _format_uptime(seconds: int) -> str:
    days, remaining = divmod(max(0, int(seconds)), 24 * 60 * 60)
    hours, remaining = divmod(remaining, 60 * 60)
    minutes, secs = divmod(remaining, 60)
    prefix = f"{days}天 " if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"


class StatusCenterTab(BaseTab):
    METRICS = [
        ("state", "客户端状态"),
        ("uptime", "运行时间"),
        ("connected_runtimes", "已连接账号"),
        ("received_messages", "收到消息"),
        ("sent_messages", "已发回复"),
        ("handoffs", "转人工"),
        ("reconnects", "自动重连"),
        ("error_runtimes", "异常账号"),
    ]

    STATE_NAMES = {
        "running": "运行中",
        "degraded": "部分异常",
        "stopping": "正在停止",
        "stopped": "已停止",
    }

    def __init__(self, master, app):
        super().__init__(master, app)
        self.labels: dict[str, ttk.Label] = {}
        grid = ttk.Frame(self)
        grid.pack(fill=tk.X)
        for index, (key, title) in enumerate(self.METRICS):
            card = ttk.LabelFrame(grid, text=title, padding=14)
            card.grid(row=index // 4, column=index % 4, sticky="nsew", padx=5, pady=5)
            label = ttk.Label(card, text="-", font=("Microsoft YaHei UI", 18, "bold"))
            label.pack()
            self.labels[key] = label
        for column in range(4):
            grid.columnconfigure(column, weight=1)

        actions = ttk.Frame(self, padding=(4, 14))
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="立即备份", command=self.backup_now).pack(side=tk.LEFT)
        ttk.Button(actions, text="打开数据目录", command=self.open_data_directory).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="刷新状态", command=self.refresh).pack(side=tk.LEFT)

        details = ttk.LabelFrame(self, text="运行详情", padding=12)
        details.pack(fill=tk.X, padx=4, pady=4)
        self.detail_labels: dict[str, ttk.Label] = {}
        for row, (key, title) in enumerate(
            [
                ("started_at", "启动时间"),
                ("last_backup_at", "最近备份"),
                ("next_backup_at", "下次备份"),
                ("last_backup_path", "备份文件"),
                ("latest_operation_at", "最近操作"),
                ("last_error", "最近错误"),
            ]
        ):
            ttk.Label(details, text=f"{title}：").grid(row=row, column=0, sticky=tk.NW, pady=3)
            label = ttk.Label(details, text="-", wraplength=980)
            label.grid(row=row, column=1, sticky=tk.W, pady=3)
            self.detail_labels[key] = label
        details.columnconfigure(1, weight=1)

    def refresh(self) -> None:
        center = self.app.status_center
        if center is None:
            return
        values = center.snapshot()
        values["state"] = self.STATE_NAMES.get(values["state"], values["state"])
        values["uptime"] = _format_uptime(values["uptime_seconds"])
        for key, label in self.labels.items():
            label.configure(text=str(values.get(key, 0)))
        for key, label in self.detail_labels.items():
            label.configure(text=str(values.get(key) or "-"))

    def backup_now(self) -> None:
        runtime = self.app.runtime
        if runtime is None:
            messagebox.showwarning("无法备份", "当前客户端运行时不可用。", parent=self)
            return
        self.app.run_background(
            "正在备份数据…",
            runtime.backup_now,
            lambda path: messagebox.showinfo("备份完成", f"备份已保存到：\n{path}", parent=self),
        )

    def open_data_directory(self) -> None:
        runtime = self.app.runtime
        if runtime is None:
            return
        path = runtime.paths.root
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("数据目录", str(path), parent=self)


class OperationsLogTab(BaseTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        self.category_var = tk.StringVar(value="")
        self.result_var = tk.StringVar(value="")
        ttk.Label(toolbar, text="分类：").pack(side=tk.LEFT)
        ttk.Combobox(
            toolbar,
            textvariable=self.category_var,
            values=["", "application", "runtime", "conversation", "decision", "channel", "backup"],
            state="readonly",
            width=16,
        ).pack(side=tk.LEFT)
        ttk.Label(toolbar, text="结果：").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Combobox(
            toolbar,
            textvariable=self.result_var,
            values=["", "success", "warning", "error", "ignored"],
            state="readonly",
            width=12,
        ).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side=tk.LEFT, padx=8)

        pane = ttk.Panedwindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        self.table = TableFrame(
            pane,
            [
                ("timestamp", "时间", 180),
                ("category", "分类", 110),
                ("action", "动作", 160),
                ("result", "结果", 90),
                ("shop", "店铺", 100),
                ("conversation", "会话", 160),
                ("summary", "说明", 360),
            ],
        )
        pane.add(self.table, weight=3)
        self.details = tk.Text(pane, height=10, wrap=tk.WORD, state=tk.DISABLED)
        pane.add(self.details, weight=2)
        self.table.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_details())

    def refresh(self) -> None:
        operation_log = self.app.operation_log
        if operation_log is None:
            self.table.set_rows([], [])
            return
        rows = operation_log.list_recent(
            limit=1000,
            category=self.category_var.get(),
            result=self.result_var.get(),
        )
        display = [
            {
                **row,
                "id": row["event_id"],
                "shop": row.get("shop_key", ""),
                "conversation": row.get("conversation_id", ""),
            }
            for row in rows
        ]
        self.table.set_rows(
            display,
            ["timestamp", "category", "action", "result", "shop", "conversation", "summary"],
        )
        self.show_details()

    def show_details(self) -> None:
        row = self.table.selected()
        content = json.dumps(row or {}, ensure_ascii=False, indent=2)
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert(tk.END, content)
        self.details.configure(state=tk.DISABLED)
