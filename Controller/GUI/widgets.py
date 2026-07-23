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
        self.summary = QtWidgets.QLabel()
        self.summary.setProperty("fieldHelp", True)
        self.summary.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred
        )
        header.addWidget(self.summary, 1)

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
        self.container.updateGeometry()
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()

    def layout_for_rows(self) -> QtWidgets.QVBoxLayout:
        return self.vbox

    def set_summary(self, text: str) -> None:
        self.summary.setText(text)
        self.summary.setToolTip(text)

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
