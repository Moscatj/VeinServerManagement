"""
Shared Qt widgets for Vein Manager GUI helpers.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class CollapsibleBox(QtWidgets.QWidget):
    """Simple collapsible section with a header and a container layout."""

    def __init__(self, title: str):
        super().__init__()
        self._title_base = title
        self._count = 0

        self.toggle = QtWidgets.QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(QtCore.Qt.DownArrow)
        self.toggle.toggled.connect(self._on_toggled)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle)
        header.addStretch(1)

        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(8, 6, 8, 6)
        self.vbox.setSpacing(6)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.addLayout(header)
        outer.addWidget(self.container)

    def _on_toggled(self, on: bool):
        self.container.setVisible(on)
        self.toggle.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)

    def layout_for_rows(self) -> QtWidgets.QVBoxLayout:
        return self.vbox

    def set_count(self, n: int, active: bool):
        """Update header with a small count when filtering."""
        self._count = n
        suffix = f"  ({n})" if active else ""
        self.toggle.setText(self._title_base + suffix)

    def setContentLayout(self, layout: QtWidgets.QLayout):
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        self.vbox = (
            layout
            if isinstance(layout, QtWidgets.QVBoxLayout)
            else QtWidgets.QVBoxLayout(self.container)
        )
        self.container.setLayout(self.vbox)

