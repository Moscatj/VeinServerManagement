"""
Panel builders for Vein Manager (command bar, left column, log tail, placeholders).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PySide6 import QtCore, QtWidgets

from .widgets import CollapsibleBox

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def build_command_bar(
    owner: "Main", dot_style: Callable[[bool, bool], str]
) -> QtWidgets.QWidget:
    bar = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    def build_dot() -> QtWidgets.QLabel:
        dot = QtWidgets.QLabel()
        dot.setFixedSize(14, 14)
        dot.setStyleSheet(dot_style(False))
        return dot

    owner.dot_srv = build_dot()
    owner.dot_lm = build_dot()
    owner.dot_cm = build_dot()

    owner.b_start = QtWidgets.QPushButton("Start Server")
    owner.b_stop = QtWidgets.QPushButton("Stop Server")
    owner.b_restart = QtWidgets.QPushButton("Restart")
    owner.b_lm_on = QtWidgets.QPushButton("Start Log Monitor")
    owner.b_lm_off = QtWidgets.QPushButton("Stop Log Monitor")
    owner.b_cm_on = QtWidgets.QPushButton("Start Crash Monitor")
    owner.b_cm_off = QtWidgets.QPushButton("Stop Crash Monitor")

    def build_cluster(label: str, dot: QtWidgets.QLabel, buttons: list[QtWidgets.QWidget]):
        layout.addWidget(QtWidgets.QLabel(label))
        layout.addWidget(dot)
        for btn in buttons:
            layout.addWidget(btn)
        layout.addSpacing(10)

    build_cluster("Server", owner.dot_srv, [owner.b_start, owner.b_stop, owner.b_restart])
    build_cluster("LogMon", owner.dot_lm, [owner.b_lm_on, owner.b_lm_off])
    build_cluster("CrashMon", owner.dot_cm, [owner.b_cm_on, owner.b_cm_off])

    layout.addStretch(1)
    owner.status_label = QtWidgets.QLabel("Status: Idle")
    owner.status_label.setWordWrap(True)
    owner.status_label.setTextInteractionFlags(
        QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
    )
    layout.addWidget(owner.status_label)
    owner.status = owner.status_label  # legacy attribute
    return bar


def build_left_panel(owner: "Main", nav_panel: QtWidgets.QWidget) -> QtWidgets.QWidget:
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    width_hint = max(nav_panel.sizeHint().width(), 140)
    nav_panel.setMinimumWidth(width_hint)
    nav_panel.setMaximumWidth(width_hint)
    nav_panel.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
    nav_panel.setProperty("fixed_width", width_hint)
    layout.addWidget(nav_panel, 1)
    return panel


def build_log_panel(owner: "Main") -> QtWidgets.QWidget:
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    controls = QtWidgets.QHBoxLayout()
    owner.chk_live = QtWidgets.QCheckBox("Live (follow)")
    owner.chk_live.setChecked(True)
    owner.b_clearlog = QtWidgets.QPushButton("Clear")
    controls.addWidget(owner.chk_live)
    controls.addStretch(1)
    controls.addWidget(owner.b_clearlog)
    layout.addLayout(controls)

    owner.logTabs = QtWidgets.QTabWidget()
    owner.log_game = QtWidgets.QPlainTextEdit()
    owner.log_game.setReadOnly(True)
    owner.log_game.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    owner.log_lm = QtWidgets.QPlainTextEdit()
    owner.log_lm.setReadOnly(True)
    owner.log_lm.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    owner.log_cm = QtWidgets.QPlainTextEdit()
    owner.log_cm.setReadOnly(True)
    owner.log_cm.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    owner.logTabs.addTab(owner.log_game, "Game Log")
    owner.logTabs.addTab(owner.log_lm, "Log Monitor")
    owner.logTabs.addTab(owner.log_cm, "Crash Monitor")

    owner.log_search_tab = QtWidgets.QWidget()
    search_layout = QtWidgets.QVBoxLayout(owner.log_search_tab)
    search_layout.setContentsMargins(4, 4, 4, 4)
    search_layout.setSpacing(6)

    filters = QtWidgets.QGridLayout()
    filters.setHorizontalSpacing(6)
    filters.setVerticalSpacing(4)

    owner.cmb_log_sources = QtWidgets.QComboBox()
    owner.cmb_log_sources.addItem("All subsystems", "__all__")
    owner.btn_log_src_refresh = QtWidgets.QPushButton("Reload")
    owner.ed_log_search = QtWidgets.QLineEdit()
    owner.ed_log_search.setPlaceholderText("Regex or plain text")
    owner.cmb_log_since = QtWidgets.QComboBox()
    owner.cmb_log_since.addItem("Any time", "")
    owner.cmb_log_since.addItem("Last hour", "1h")
    owner.cmb_log_since.addItem("Last 6 hours", "6h")
    owner.cmb_log_since.addItem("Last day", "24h")
    owner.spin_log_limit = QtWidgets.QSpinBox()
    owner.spin_log_limit.setRange(10, 2000)
    owner.spin_log_limit.setValue(200)
    owner.chk_log_case = QtWidgets.QCheckBox("Case sensitive")
    owner.chk_log_include_archive = QtWidgets.QCheckBox("Include archive")
    owner.btn_log_search = QtWidgets.QPushButton("Search")
    owner.btn_log_search_clear = QtWidgets.QPushButton("Clear")
    owner.log_search_status = QtWidgets.QLabel("Idle")

    filters.addWidget(QtWidgets.QLabel("Subsystem:"), 0, 0)
    filters.addWidget(owner.cmb_log_sources, 0, 1)
    filters.addWidget(owner.btn_log_src_refresh, 0, 2)

    filters.addWidget(QtWidgets.QLabel("Query:"), 1, 0)
    filters.addWidget(owner.ed_log_search, 1, 1, 1, 2)

    filters.addWidget(QtWidgets.QLabel("Since:"), 2, 0)
    filters.addWidget(owner.cmb_log_since, 2, 1)
    filters.addWidget(QtWidgets.QLabel("Max hits:"), 2, 2)
    filters.addWidget(owner.spin_log_limit, 2, 3)
    filters.addWidget(owner.chk_log_include_archive, 2, 4)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addWidget(owner.chk_log_case)
    btn_row.addStretch(1)
    btn_row.addWidget(owner.btn_log_search)
    btn_row.addWidget(owner.btn_log_search_clear)

    owner.log_search_results = QtWidgets.QPlainTextEdit()
    owner.log_search_results.setReadOnly(True)
    owner.log_search_results.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

    search_layout.addLayout(filters)
    search_layout.addLayout(btn_row)
    search_layout.addWidget(owner.log_search_results, 1)
    search_layout.addWidget(owner.log_search_status)

    owner.logTabs.addTab(owner.log_search_tab, "Search Logs")

    owner.mgmt_log_tab = QtWidgets.QWidget()
    mgmt_layout = QtWidgets.QVBoxLayout(owner.mgmt_log_tab)
    mgmt_layout.setContentsMargins(4, 4, 4, 4)
    mgmt_layout.setSpacing(6)

    mgmt_controls = QtWidgets.QGridLayout()
    mgmt_controls.setHorizontalSpacing(6)
    mgmt_controls.setVerticalSpacing(4)

    owner.cmb_mgmt_log_subsystem = QtWidgets.QComboBox()
    owner.cmb_mgmt_log_subsystem.addItem("Select subsystem", "__none__")
    owner.btn_mgmt_log_refresh = QtWidgets.QPushButton("Refresh")
    owner.cmb_mgmt_log_file = QtWidgets.QComboBox()
    owner.btn_mgmt_log_load = QtWidgets.QPushButton("Load")
    owner.btn_mgmt_log_open = QtWidgets.QPushButton("Open Folder")
    owner.btn_mgmt_archive = QtWidgets.QPushButton("Archive Logs")

    mgmt_controls.addWidget(QtWidgets.QLabel("Subsystem:"), 0, 0)
    mgmt_controls.addWidget(owner.cmb_mgmt_log_subsystem, 0, 1)
    mgmt_controls.addWidget(owner.btn_mgmt_log_refresh, 0, 2)
    mgmt_controls.addWidget(owner.btn_mgmt_archive, 0, 3)
    mgmt_controls.addWidget(QtWidgets.QLabel("Log file:"), 1, 0)
    mgmt_controls.addWidget(owner.cmb_mgmt_log_file, 1, 1)
    mgmt_controls.addWidget(owner.btn_mgmt_log_load, 1, 2)
    mgmt_controls.addWidget(owner.btn_mgmt_log_open, 1, 3)

    owner.txt_mgmt_log = QtWidgets.QPlainTextEdit()
    owner.txt_mgmt_log.setReadOnly(True)
    owner.txt_mgmt_log.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)

    mgmt_layout.addLayout(mgmt_controls)
    mgmt_layout.addWidget(owner.txt_mgmt_log, 1)

    owner.logTabs.addTab(owner.mgmt_log_tab, "Subsystem Log")

    owner.log_errors_tab = QtWidgets.QWidget()
    err_layout = QtWidgets.QVBoxLayout(owner.log_errors_tab)
    err_layout.setContentsMargins(4, 4, 4, 4)
    err_layout.setSpacing(6)

    err_controls = QtWidgets.QGridLayout()
    err_controls.setHorizontalSpacing(6)
    err_controls.setVerticalSpacing(4)

    owner.cmb_error_subsystem = QtWidgets.QComboBox()
    owner.cmb_error_subsystem.addItem("All subsystems", "__all__")
    owner.cmb_error_since = QtWidgets.QComboBox()
    owner.cmb_error_since.addItem("Any time", "")
    owner.cmb_error_since.addItem("Last hour", "1h")
    owner.cmb_error_since.addItem("Last 6 hours", "6h")
    owner.cmb_error_since.addItem("Last 24 hours", "24h")
    owner.cmb_error_since.addItem("Last 7 days", "7d")
    owner.cmb_error_since.setCurrentIndex(2)
    owner.spin_error_limit = QtWidgets.QSpinBox()
    owner.spin_error_limit.setRange(10, 1000)
    owner.spin_error_limit.setValue(200)
    owner.btn_error_refresh = QtWidgets.QPushButton("Refresh")
    owner.lbl_error_status = QtWidgets.QLabel("Idle")
    owner.chk_error_include_archive = QtWidgets.QCheckBox("Include archive")

    err_controls.addWidget(QtWidgets.QLabel("Subsystem:"), 0, 0)
    err_controls.addWidget(owner.cmb_error_subsystem, 0, 1)
    err_controls.addWidget(QtWidgets.QLabel("Since:"), 1, 0)
    err_controls.addWidget(owner.cmb_error_since, 1, 1)
    err_controls.addWidget(QtWidgets.QLabel("Max events:"), 1, 2)
    err_controls.addWidget(owner.spin_error_limit, 1, 3)
    err_controls.addWidget(owner.chk_error_include_archive, 2, 0, 1, 2)
    err_controls.addWidget(owner.btn_error_refresh, 2, 3)

    owner.tbl_error_events = QtWidgets.QTableWidget(0, 5)
    owner.tbl_error_events.setHorizontalHeaderLabels(
        ["Subsystem", "Timestamp", "File", "Level", "Message"]
    )
    owner.tbl_error_events.horizontalHeader().setStretchLastSection(True)
    owner.tbl_error_events.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    owner.tbl_error_events.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    owner.tbl_error_events.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    err_layout.addLayout(err_controls)
    err_layout.addWidget(owner.tbl_error_events, 1)
    err_layout.addWidget(owner.lbl_error_status)

    owner.logTabs.addTab(owner.log_errors_tab, "Errors")
    layout.addWidget(owner.logTabs, 1)
    return panel


def build_placeholder_view(message: str) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.addStretch(1)
    label = QtWidgets.QLabel(message)
    label.setWordWrap(True)
    label.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(label)
    layout.addStretch(1)
    return widget
