from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from .admin import AdminService
from .db import create_database
from .desktop_catalog import KnowledgeTab, ModelsTab, RulesTab, UnknownTab
from .desktop_operations import ChannelsTab, ConversationsTab, HandoffsTab, OverviewTab, SettingsTab
from .runtime_status import RuntimeStatusRegistry


class DesktopApp(tk.Tk):
    def __init__(self, admin: AdminService, registry: RuntimeStatusRegistry | None = None):
        super().__init__()
        self.admin = admin
        self.registry = registry or RuntimeStatusRegistry()
        self.title("AI Customer Service 管理后台")
        self.geometry("1380x850")
        self.minsize(1120, 680)

        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill=tk.X)
        ttk.Label(top, text="当前店铺：").pack(side=tk.LEFT)
        self.shop_var = tk.StringVar(value="demo")
        self.shop_box = ttk.Combobox(top, textvariable=self.shop_var, width=28)
        self.shop_box.pack(side=tk.LEFT, padx=(0, 8))
        self.shop_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_all())
        ttk.Button(top, text="刷新全部", command=self.refresh_all).pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.views = [
            OverviewTab(self.tabs, self), ModelsTab(self.tabs, self), UnknownTab(self.tabs, self),
            KnowledgeTab(self.tabs, self), RulesTab(self.tabs, self), ConversationsTab(self.tabs, self),
            HandoffsTab(self.tabs, self), SettingsTab(self.tabs, self), ChannelsTab(self.tabs, self),
        ]
        titles = ["总览", "型号库", "未知型号", "知识库", "自动规则", "会话", "转人工", "店铺设置", "渠道账号"]
        for view, title in zip(self.views, titles):
            self.tabs.add(view, text=title)
        self.refresh_shop_list()
        self.refresh_all()

    @property
    def shop_key(self) -> str:
        return self.shop_var.get().strip() or "demo"

    def refresh_shop_list(self) -> None:
        shops = self.admin.list_shops()
        if self.shop_key not in shops:
            shops.insert(0, self.shop_key)
        self.shop_box["values"] = shops

    def refresh_all(self) -> None:
        self.refresh_shop_list()
        for view in self.views:
            try:
                view.refresh()
            except Exception as exc:
                self.status_var.set(f"刷新失败：{exc}")

    def run_background(self, label: str, operation: Callable[[], Any], on_success: Callable[[Any], None] | None = None) -> None:
        self.status_var.set(label)

        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:
                self.after(0, lambda: self._show_error(label, exc))
                return
            self.after(0, lambda: self._finish_background(result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, label: str, exc: Exception) -> None:
        self.status_var.set("操作失败")
        messagebox.showerror(label, str(exc), parent=self)

    def _finish_background(self, result: Any, on_success: Callable[[Any], None] | None) -> None:
        self.status_var.set("完成")
        if on_success:
            on_success(result)
        self.refresh_all()


def main() -> None:
    db_path = Path(os.getenv("AI_STORE_DB", "data/ai-store-support.db"))
    engine, sessions = create_database(db_path)
    DesktopApp(AdminService(sessions, engine)).mainloop()


if __name__ == "__main__":
    main()
