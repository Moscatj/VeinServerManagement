"""Navigation helpers for Vein Manager's authoritative page stack."""

from __future__ import annotations

from typing import Callable

from PySide6 import QtWidgets


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
