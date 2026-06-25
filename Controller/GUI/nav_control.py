"""
Navigation and pinning helpers for Vein Manager.

This controller centralizes view registration and pinning so the main window
stays smaller.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets


class NavigationController:
    def __init__(self, owner) -> None:
        self.owner = owner

    def register_view(
        self,
        view_id: str,
        widget: QtWidgets.QWidget,
        on_show: Callable[[], None] | None = None,
    ) -> None:
        owner = self.owner
        if owner.content_stack.indexOf(widget) < 0:
            owner.content_stack.addWidget(widget)
        owner._view_routes[view_id] = (widget, on_show)

    def on_view_selected(self, view_id: str) -> None:
        owner = self.owner
        target = getattr(owner, "_view_routes", {}).get(view_id)
        if not target:
            return
        widget, callback = target
        idx = owner.content_stack.indexOf(widget)
        if idx >= 0:
            owner.content_stack.setCurrentIndex(idx)
        if callback:
            callback()

    def nav_context_menu(
        self, list_widget: QtWidgets.QListWidget, pos: QtCore.QPoint
    ) -> None:
        owner = self.owner
        item = list_widget.itemAt(pos)
        if not item:
            return
        view_id = item.data(QtCore.Qt.UserRole)
        label = item.text()
        menu = QtWidgets.QMenu(owner)
        act_right = menu.addAction(f"Open '{label}' in side panel")
        act_center = menu.addAction(f"Open '{label}' in center panel")
        chosen = menu.exec(list_widget.viewport().mapToGlobal(pos))
        if chosen == act_right:
            self.pin_view_to_side_tabs(view_id, label)
        elif chosen == act_center:
            self.pin_view_to_center(view_id)

    def pin_view_to_side_tabs(self, view_id: str, label: str) -> None:
        owner = self.owner
        if view_id == "monitor.logs":
            self.ensure_tab_present("Logs", None)
            return
        if view_id == "monitor.config":
            self.ensure_tab_present("Config", None)
            return
        if view_id == "monitor.discord":
            self.ensure_tab_present("Discord", owner._view_factories.get(view_id))
            return
        factory = owner._view_factories.get(view_id)
        if not factory:
            return
        widget = factory()
        tab_label = label
        existing = [owner.side_tabs.tabText(i) for i in range(owner.side_tabs.count())]
        suffix = 2
        while tab_label in existing:
            tab_label = f"{label} ({suffix})"
            suffix += 1
        owner.side_tabs.addTab(widget, tab_label)
        owner.side_tabs.setCurrentWidget(widget)

    def pin_view_to_center(self, view_id: str) -> None:
        owner = self.owner
        target = getattr(owner, "_view_routes", {}).get(view_id)
        if target:
            widget, callback = target
            if owner.content_stack.indexOf(widget) >= 0:
                owner.content_stack.setCurrentWidget(widget)
                if callback:
                    callback()
                return
        factory = owner._view_factories.get(view_id)
        if not factory:
            return
        widget = factory()
        self.register_view(view_id, widget)
        owner.content_stack.setCurrentWidget(widget)

    def ensure_tab_present(
        self, label: str, factory: Optional[Callable[[], QtWidgets.QWidget]]
    ) -> None:
        owner = self.owner
        for i in range(owner.side_tabs.count()):
            if owner.side_tabs.tabText(i) == label:
                owner.side_tabs.setCurrentIndex(i)
                owner._set_right_panel_visible(True)
                return
        widget = owner._side_tab_store.get(label)
        if widget is None and factory:
            widget = factory()
        if widget is None:
            return
        owner.side_tabs.addTab(widget, label)
        owner.side_tabs.setCurrentWidget(widget)
        owner._side_tab_store[label] = widget
