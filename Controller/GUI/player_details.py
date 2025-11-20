"""
Helpers for the player / character detail dialogs.
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from PySide6 import QtCore, QtWidgets, QtGui

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def handle_player_tree_double_click(owner: "Main", item, column) -> None:
    payload = item.data(0, QtCore.Qt.UserRole)
    if not isinstance(payload, dict):
        return
    kind = payload.get("type")
    raw = payload.get("data") or {}
    if kind == "player":
        title = f"Player {raw.get('name') or raw.get('steam_id')}"
    elif kind == "character":
        title = f"Character {raw.get('name') or raw.get('character_id')}"
    else:
        title = "Details"
    show_json_dialog(owner, title, raw)


def show_json_dialog(parent: QtWidgets.QWidget, title: str, payload: Any) -> None:
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title or "Details")
    layout = QtWidgets.QVBoxLayout(dlg)

    tabs = QtWidgets.QTabWidget()
    tree = QtWidgets.QTreeWidget()
    tree.setHeaderLabels(["Key", "Value"])
    tree.setUniformRowHeights(True)
    populate_json_tree(tree.invisibleRootItem(), payload)
    tree.expandToDepth(1)
    tabs.addTab(tree, "Tree")

    raw_view = QtWidgets.QPlainTextEdit()
    raw_view.setReadOnly(True)
    try:
        json_text = json.dumps(payload, indent=2, sort_keys=True)
    except Exception:
        json_text = str(payload)
    raw_view.setPlainText(json_text)
    tabs.addTab(raw_view, "Raw JSON")
    layout.addWidget(tabs)

    btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    copy_btn = btn_box.addButton("Copy JSON", QtWidgets.QDialogButtonBox.ActionRole)
    copy_btn.clicked.connect(
        lambda: QtWidgets.QApplication.clipboard().setText(json_text)
    )
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    layout.addWidget(btn_box)

    dlg.resize(750, 550)
    dlg.exec()


def populate_json_tree(
    parent_item: QtWidgets.QTreeWidgetItem, value: Any, key: str = ""
) -> None:
    if isinstance(value, dict):
        node = QtWidgets.QTreeWidgetItem(parent_item, [key or "object", ""])
        for sub_key, sub_val in value.items():
            populate_json_tree(node, sub_val, str(sub_key))
    elif isinstance(value, list):
        label = f"{key} [{len(value)}]" if key else f"array[{len(value)}]"
        node = QtWidgets.QTreeWidgetItem(parent_item, [label, ""])
        for idx, item in enumerate(value):
            populate_json_tree(node, item, f"[{idx}]")
    else:
        display = (
            json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        )
        QtWidgets.QTreeWidgetItem(parent_item, [key or "value", display])

