"""
Config editor builder for Vein Manager.

Contains a helper that builds the tabbed config editor UI while reusing
the existing attributes on `Main`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def build_config_editor(owner: "Main") -> QtWidgets.QWidget:
    page = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    topbar = QtWidgets.QHBoxLayout()
    owner.b_reload = QtWidgets.QPushButton("Reload Config")
    owner.b_validate = QtWidgets.QPushButton("Validate")
    owner.b_save = QtWidgets.QPushButton("Save Config (atomic)")
    owner.filter = QtWidgets.QLineEdit()
    owner.filter.setPlaceholderText("Filter keys…")
    owner.b_clearfilter = QtWidgets.QPushButton("Clear")
    topbar.addWidget(owner.b_reload)
    topbar.addWidget(owner.b_validate)
    topbar.addWidget(owner.b_save)
    topbar.addStretch(1)
    topbar.addWidget(owner.filter)
    topbar.addWidget(owner.b_clearfilter)
    layout.addLayout(topbar)

    splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
    layout.addWidget(splitter, 1)

    tabs_container = QtWidgets.QWidget()
    tabs_layout = QtWidgets.QVBoxLayout(tabs_container)
    tabs_layout.setContentsMargins(0, 0, 0, 0)
    tabs_layout.setSpacing(0)

    owner.tabs = QtWidgets.QTabWidget()
    tabs_layout.addWidget(owner.tabs, 1)
    splitter.addWidget(tabs_container)

    owner.tab_widgets = {}
    owner.tab_layouts = {}
    owner._tab_pages = {}

    def _make_tab_ui():
        w = QtWidgets.QWidget()
        frame = QtWidgets.QVBoxLayout(w)
        frame.setContentsMargins(6, 6, 6, 6)
        frame.setSpacing(6)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        scroll.setWidget(container)
        frame.addWidget(scroll, 1)
        return w, container, vbox

    def _add_tab(name: str):
        if name in owner.tab_widgets:
            return
        w, container, vbox = _make_tab_ui()
        owner.tabs.addTab(w, name)
        owner._tab_pages[name] = w
        owner.tab_widgets[name] = container
        owner.tab_layouts[name] = vbox

    owner._add_tab = _add_tab  # expose helper for dynamic tab building
    for name in [
        "Paths",
        "Server",
        "Steam/Updates",
        "Backups",
        "Monitor (simple)",
        "Monitor (advanced)",
        "Features",
        "Top-level",
    ]:
        _add_tab(name)

    owner._tab_base_titles = {
        i: owner.tabs.tabText(i) for i in range(owner.tabs.count())
    }
    owner._tab_index_to_name = {
        i: owner._tab_base_titles[i] for i in range(owner.tabs.count())
    }

    owner.json = QtWidgets.QPlainTextEdit()
    owner.json.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    owner.json.setFont(QtGui.QFont("Consolas", 10))
    splitter.addWidget(owner.json)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 1)

    return page
