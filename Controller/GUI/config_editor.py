"""
Config editor builder for Vein Manager.

Contains a helper that builds the tabbed config editor UI while reusing
the existing attributes on `Main`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from .design_system import PAGE_MARGIN, SECTION_SPACING, PageHeader
from .widgets import CollapsibleBox

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def build_config_editor(owner: "Main") -> QtWidgets.QWidget:
    page = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(page)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.addWidget(
        PageHeader(
            "Advanced Config",
            "Inspect and edit the management configuration. Validate changes before saving.",
        )
    )

    cfg_box = CollapsibleBox("Config Source")
    cfg_box.toggle.setChecked(False)
    cfg_grid = QtWidgets.QGridLayout()
    cfg_grid.setContentsMargins(4, 0, 4, 6)
    cfg_grid.setHorizontalSpacing(6)
    cfg_grid.setVerticalSpacing(4)

    owner.ed_cfgdir = QtWidgets.QLineEdit(owner.config_dir)
    owner.b_cfgdir = QtWidgets.QPushButton("Browse…")
    owner.b_cfgdir.setFixedWidth(110)
    owner.b_reload_cfgs = QtWidgets.QPushButton("Refresh")
    owner.b_reload_cfgs.setFixedWidth(80)
    cfg_grid.addWidget(QtWidgets.QLabel("Folder:"), 0, 0)
    cfg_grid.addWidget(owner.ed_cfgdir, 0, 1)
    cfg_grid.addWidget(owner.b_cfgdir, 0, 2)

    owner.cb_cfg = QtWidgets.QComboBox()
    owner.cb_cfg.setMinimumWidth(220)
    owner.cb_cfg.setSizeAdjustPolicy(
        QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
    )
    owner.cb_cfg.setMinimumContentsLength(20)
    cfg_grid.addWidget(QtWidgets.QLabel("Config:"), 1, 0)
    cfg_grid.addWidget(owner.cb_cfg, 1, 1)
    cfg_grid.addWidget(owner.b_reload_cfgs, 1, 2)

    cfg_inner = cfg_box.layout_for_rows()
    cfg_inner.addLayout(cfg_grid)
    layout.addWidget(cfg_box)

    topbar = QtWidgets.QHBoxLayout()
    owner.b_reload = QtWidgets.QPushButton("Reload Config")
    owner.b_validate = QtWidgets.QPushButton("Validate")
    owner.b_save = QtWidgets.QPushButton("Save Config (atomic)")
    owner.filter = QtWidgets.QLineEdit()
    owner.filter.setPlaceholderText("Filter keys…")
    owner.b_clearfilter = QtWidgets.QPushButton("Clear")
    owner.btn_toggle_raw = QtWidgets.QToolButton()
    owner.btn_toggle_raw.setText("Show Raw YAML/JSON")
    owner.btn_toggle_raw.setCheckable(True)
    owner.btn_toggle_raw.setChecked(False)
    topbar.addWidget(owner.b_reload)
    topbar.addWidget(owner.b_validate)
    topbar.addWidget(owner.b_save)
    topbar.addStretch(1)
    topbar.addWidget(owner.filter)
    topbar.addWidget(owner.b_clearfilter)
    topbar.addWidget(owner.btn_toggle_raw)
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
    owner.json.hide()
    splitter.setSizes([1, 0])

    def _toggle_raw_editor(checked: bool):
        owner.json.setVisible(checked)
        owner.btn_toggle_raw.setText("Hide Raw YAML/JSON" if checked else "Show Raw YAML/JSON")
        if checked:
            splitter.setSizes([2, 1])
        else:
            splitter.setSizes([1, 0])

    owner.btn_toggle_raw.toggled.connect(_toggle_raw_editor)

    return page
