from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .desktop import DesktopApp


class TableFrame(ttk.Frame):
    def __init__(self, master, columns: list[tuple[str, str, int]]):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=[item[0] for item in columns], show="headings", selectmode="browse")
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60, anchor=tk.W)
        ybar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        xbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rows: dict[str, dict[str, Any]] = {}

    def set_rows(self, rows: list[dict[str, Any]], value_keys: list[str]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.rows.clear()
        for index, row in enumerate(rows):
            item_id = str(row.get("id", f"row-{index}"))
            if item_id in self.rows:
                item_id = f"{item_id}-{index}"
            self.rows[item_id] = row
            self.tree.insert("", tk.END, iid=item_id, values=[row.get(key, "") for key in value_keys])

    def selected(self) -> dict[str, Any] | None:
        selected = self.tree.selection()
        return self.rows.get(selected[0]) if selected else None


class BaseTab(ttk.Frame):
    def __init__(self, master, app: DesktopApp):
        super().__init__(master, padding=10)
        self.app = app

    @property
    def admin(self):
        return self.app.admin

    @property
    def shop(self) -> str:
        return self.app.shop_key

    def refresh(self) -> None:
        pass

    def require_row(self, table: TableFrame) -> dict[str, Any] | None:
        row = table.selected()
        if row is None:
            messagebox.showinfo("请选择记录", "请先在表格中选择一条记录。", parent=self)
        return row
