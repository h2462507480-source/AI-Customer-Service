from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from .admin import AdminService
from .application_runtime import ApplicationRuntime
from .client_status import ClientStatusCenter
from .desktop_catalog import KnowledgeTab, ModelsTab, RulesTab, UnknownTab
from .desktop_operations import ChannelsTab, ConversationsTab, HandoffsTab, OverviewTab, SettingsTab
from .desktop_runtime import OperationsLogTab, StatusCenterTab
from .operation_log import OperationLog
from .runtime_status import RuntimeStatusRegistry


class DesktopApp(tk.Tk):
    def __init__(
        self,
        admin: AdminService,
        registry: RuntimeStatusRegistry | None = None,
        *,
        runtime: ApplicationRuntime | None = None,
        operation_log: OperationLog | None = None,
        status_center: ClientStatusCenter | None = None,
    ):
        super().__init__()
        self.admin = admin
        self.registry = registry or RuntimeStatusRegistry()
        self.runtime = runtime
        self.operation_log = operation_log or (runtime.operation_log if runtime else None)
        self.status_center = status_center or (runtime.status_center if runtime else None)
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
            StatusCenterTab(self.tabs, self), OverviewTab(self.tabs, self),
            ModelsTab(self.tabs, self), UnknownTab(self.tabs, self),
            KnowledgeTab(self.tabs, self), RulesTab(self.tabs, self), ConversationsTab(self.tabs, self),
            HandoffsTab(self.tabs, self), OperationsLogTab(self.tabs, self),
            SettingsTab(self.tabs, self), ChannelsTab(self.tabs, self),
        ]
        titles = [
            "运行中心", "业务总览", "型号库", "未知型号", "知识库", "自动规则",
            "会话", "转人工", "操作日志", "店铺设置", "渠道账号",
        ]
        for view, title in zip(self.views, titles):
            self.tabs.add(view, text=title)
        self.refresh_shop_list()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(1000, self._poll_status)

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

    def _poll_status(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self.views[0].refresh()
        finally:
            self.after(1000, self._poll_status)

    def close(self) -> None:
        try:
            if self.runtime:
                self.runtime.stop()
        finally:
            self.destroy()


def main() -> None:
    runtime = ApplicationRuntime()
    runtime.start()
    try:
        DesktopApp(
            runtime.admin,
            runtime.registry,
            runtime=runtime,
        ).mainloop()
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
