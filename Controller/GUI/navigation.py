"""Navigation widgets for the Vein Manager GUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from PySide6 import QtCore, QtGui, QtWidgets


class NavList(QtWidgets.QListWidget):
    """List widget that supports drag without forcing selection changes mid-drag."""

    def __init__(self, owner: "NavigationPanel", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._owner = owner

    def startDrag(self, supportedActions):  # type: ignore[override]
        item = self.currentItem()
        if not item:
            return
        view_id = item.data(QtCore.Qt.UserRole)
        if not view_id:
            return
        mime = QtCore.QMimeData()
        mime.setData("application/x-vein-view", str(view_id).encode("utf-8"))
        mime.setText(item.text())
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        self._owner._dragging = True
        try:
            drag.exec(QtCore.Qt.CopyAction)
        finally:
            self._owner._dragging = False


@dataclass(frozen=True)
class NavigationItem:
    """Simple descriptor for an entry in the left-hand navigation."""

    view_id: str
    label: str
    subtitle: str | None = None
    enabled: bool = True


class NavigationPanel(QtWidgets.QWidget):
    """
    Lightweight navigation panel with Monitoring + Configuration sections.
    """

    viewSelected = QtCore.Signal(str)

    def __init__(
        self,
        monitor_items: Iterable[NavigationItem],
        config_items: Iterable[NavigationItem],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._monitor_items = list(monitor_items)
        self._config_items = list(config_items)
        self._dragging = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._monitor_container, self.monitor_list = self._build_section(
            "Monitoring", self._monitor_items
        )
        layout.addWidget(self._monitor_container)

        self._config_container, self.config_list = self._build_section(
            "Configuration", self._config_items
        )
        layout.addWidget(self._config_container)
        if not self._config_items:
            self._config_container.hide()
        layout.addStretch(1)

        self.monitor_list.itemClicked.connect(self._emit_selected)
        self.config_list.itemClicked.connect(self._emit_selected)
        self.monitor_list.itemSelectionChanged.connect(
            lambda: self._emit_selected(self.monitor_list.currentItem())
        )
        self.config_list.itemSelectionChanged.connect(
            lambda: self._emit_selected(self.config_list.currentItem())
        )
        self.monitor_list.setDragEnabled(True)
        self.config_list.setDragEnabled(True)
        self.monitor_list.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self.config_list.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

    def _build_section(
        self, title: str, items: list[NavigationItem]
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QListWidget]:
        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        frame = QtWidgets.QGroupBox(title)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(6, 4, 6, 6)
        frame_layout.setSpacing(4)

        lst = NavList(self)
        lst.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        lst.setAlternatingRowColors(True)
        lst.setFrameShape(QtWidgets.QFrame.NoFrame)
        lst.setSizeAdjustPolicy(QtWidgets.QAbstractItemView.AdjustToContents)
        lst.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        frame_layout.addWidget(lst)

        for item in items:
            entry = QtWidgets.QListWidgetItem(item.label)
            entry.setData(QtCore.Qt.UserRole, item.view_id)
            flags = entry.flags() | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
            if not item.enabled:
                flags &= ~QtCore.Qt.ItemIsEnabled
            entry.setFlags(flags)
            if item.subtitle:
                entry.setToolTip(item.subtitle)
            lst.addItem(entry)

        container_layout.addWidget(frame)
        return container, lst

    def set_default_selection(self, view_id: str) -> None:
        """Select the navigation entry matching view_id."""
        for lst in (self.monitor_list, self.config_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.data(QtCore.Qt.UserRole) == view_id:
                    lst.setCurrentRow(i)
                    return

    def startDrag(self, supportedActions):  # type: ignore[override]
        lst: QtWidgets.QListWidget = self.sender()  # type: ignore
        if not isinstance(lst, QtWidgets.QListWidget):
            return super().startDrag(supportedActions)
        item = lst.currentItem()
        if not item:
            return
        view_id = item.data(QtCore.Qt.UserRole)
        if not view_id:
            return
        mime = QtCore.QMimeData()
        mime.setData("application/x-vein-view", str(view_id).encode("utf-8"))
        mime.setText(item.text())
        drag = QtGui.QDrag(lst)
        drag.setMimeData(mime)
        self._dragging = True
        try:
            drag.exec(QtCore.Qt.CopyAction)
        finally:
            self._dragging = False

    # ------------------------------------------------------------------ helpers
    def _emit_selected(self, item: Optional[QtWidgets.QListWidgetItem]) -> None:
        if not item or self._dragging:
            return
        view_id = item.data(QtCore.Qt.UserRole)
        if view_id:
            self.viewSelected.emit(str(view_id))
