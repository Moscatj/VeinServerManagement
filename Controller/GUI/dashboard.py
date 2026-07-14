"""
Monitoring dashboard builder for Vein Manager.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from .player_details import handle_player_tree_double_click
from .design_system import (
    BUTTON_SECONDARY,
    PAGE_MARGIN,
    SECTION_SPACING,
    InlineNotice,
    PageHeader,
    StatusBadge,
    set_button_role,
)

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def build_dashboard(owner: "Main", dot_style) -> QtWidgets.QWidget:
    dashboard = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(dashboard)
    outer.setContentsMargins(0, 0, 0, 0)

    owner.dashboardScroll = QtWidgets.QScrollArea()
    owner.dashboardScroll.setWidgetResizable(True)
    owner.dashboardScroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    content = QtWidgets.QWidget()
    content.setObjectName("dashboardContent")
    layout = QtWidgets.QVBoxLayout(content)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
    layout.addWidget(
        PageHeader(
            "Home",
            "Server health, players, safeguards, and the actions that need attention.",
        )
    )

    overview_card = QtWidgets.QGroupBox("At a Glance")
    overview_layout = QtWidgets.QGridLayout(overview_card)
    overview_layout.setHorizontalSpacing(16)
    overview_layout.setVerticalSpacing(8)
    badge_specs = (
        ("Server", "badgeHomeServer", "Checking"),
        ("Log Monitor", "badgeHomeLogMonitor", "Checking"),
        ("Crash Monitor", "badgeHomeCrashMonitor", "Checking"),
        ("Backups", "badgeHomeBackups", "Checking"),
    )
    for column, (label, attribute, initial) in enumerate(badge_specs):
        overview_layout.addWidget(QtWidgets.QLabel(label), 0, column)
        badge = StatusBadge(initial)
        badge.setMinimumWidth(92)
        setattr(owner, attribute, badge)
        overview_layout.addWidget(badge, 1, column)

    owner.noticeHomeGuidance = InlineNotice(
        "Checking server health and safeguards."
    )
    overview_layout.addWidget(owner.noticeHomeGuidance, 2, 0, 1, 4)

    def navigate(view_id: str) -> None:
        navigation = getattr(owner, "nav_panel", None)
        if navigation is not None:
            navigation.set_default_selection(view_id)
        else:
            callback = getattr(owner, "_on_view_selected", None)
            if callback is not None:
                callback(view_id)

    owner.btnHomeSetup = QtWidgets.QPushButton("Open Setup")
    owner.btnHomeLogs = QtWidgets.QPushButton("View Logs")
    set_button_role(owner.btnHomeSetup, BUTTON_SECONDARY)
    set_button_role(owner.btnHomeLogs, BUTTON_SECONDARY)
    owner.btnHomeSetup.clicked.connect(lambda: navigate("monitor.quick_start"))
    owner.btnHomeLogs.clicked.connect(lambda: navigate("monitor.logs"))
    action_row = QtWidgets.QHBoxLayout()
    action_row.addWidget(owner.btnHomeSetup)
    action_row.addWidget(owner.btnHomeLogs)
    action_row.addStretch(1)
    overview_layout.addLayout(action_row, 3, 0, 1, 4)
    layout.addWidget(overview_card)

    logCard = QtWidgets.QGroupBox("Server Activity")
    logLay = QtWidgets.QGridLayout(logCard)
    owner.lblLogDot = QtWidgets.QLabel()
    owner.lblLogDot.setFixedSize(14, 14)
    owner.lblLogDot.setStyleSheet(dot_style(False))
    owner.lblLogStatus = QtWidgets.QLabel("stopped")
    owner.lblLogLast = QtWidgets.QLabel("Last update: —")
    owner.lblLogJoin = QtWidgets.QLabel("Joinable: —")
    owner.lblLogPlayers = QtWidgets.QLabel("Players: —")
    owner.lblLogUptime = QtWidgets.QLabel("Uptime: —")
    owner.lblLogHttpStatus = QtWidgets.QLabel("HTTP API: disabled")
    owner.lblLogHttpPlayers = QtWidgets.QLabel("API Players: —")
    owner.lblLogHttpWorld = QtWidgets.QLabel("World Time: —")
    owner.lblLogHttpWeather = QtWidgets.QLabel("Weather: —")
    for lbl in (
        owner.lblLogHttpStatus,
        owner.lblLogHttpPlayers,
        owner.lblLogHttpWorld,
        owner.lblLogHttpWeather,
    ):
        lbl.setWordWrap(True)
    logLay.addWidget(owner.lblLogDot, 0, 0)
    logLay.addWidget(owner.lblLogStatus, 0, 1)
    logLay.addWidget(owner.lblLogLast, 1, 0, 1, 2)
    logLay.addWidget(owner.lblLogJoin, 2, 0, 1, 2)
    logLay.addWidget(owner.lblLogPlayers, 3, 0, 1, 2)
    logLay.addWidget(owner.lblLogUptime, 4, 0, 1, 2)
    logLay.addWidget(owner.lblLogHttpStatus, 5, 0, 1, 2)
    logLay.addWidget(owner.lblLogHttpPlayers, 6, 0, 1, 2)
    logLay.addWidget(owner.lblLogHttpWorld, 7, 0, 1, 2)
    logLay.addWidget(owner.lblLogHttpWeather, 8, 0, 1, 2)
    layout.addWidget(logCard)

    preflightCard = QtWidgets.QGroupBox("Server Preflight")
    preflightLay = QtWidgets.QVBoxLayout(preflightCard)
    owner.lblPreflightSummary = QtWidgets.QLabel("Not checked yet")
    owner.lblPreflightSummary.setWordWrap(True)
    owner.lblPreflightSummary.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    owner.lblPreflightDetails = QtWidgets.QLabel("")
    owner.lblPreflightDetails.setWordWrap(True)
    owner.lblPreflightDetails.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    owner.btnPreflightRefresh = QtWidgets.QPushButton("Refresh")
    preflightRow = QtWidgets.QHBoxLayout()
    preflightRow.addWidget(owner.btnPreflightRefresh)
    preflightRow.addStretch(1)
    preflightLay.addWidget(owner.lblPreflightSummary)
    preflightLay.addWidget(owner.lblPreflightDetails)
    preflightLay.addLayout(preflightRow)
    layout.addWidget(preflightCard)

    crashCard = QtWidgets.QGroupBox("Crash Monitor")
    cLay = QtWidgets.QGridLayout(crashCard)
    owner.lblCrashDot = QtWidgets.QLabel()
    owner.lblCrashDot.setFixedSize(14, 14)
    owner.lblCrashDot.setStyleSheet(dot_style(False))
    owner.lblCrashMode = QtWidgets.QLabel("stopped")
    owner.lblCrashLast = QtWidgets.QLabel("Last heartbeat: —")
    cLay.addWidget(owner.lblCrashDot, 0, 0)
    cLay.addWidget(owner.lblCrashMode, 0, 1)
    cLay.addWidget(owner.lblCrashLast, 1, 0, 1, 2)
    layout.addWidget(crashCard)

    playerCard = QtWidgets.QGroupBox("Players & HTTP API")
    playerLay = QtWidgets.QVBoxLayout(playerCard)
    owner.lblAdminList = QtWidgets.QLabel("Admins: …")
    owner.lblAdminList.setWordWrap(True)
    owner.lblPlayerSnapshotTs = QtWidgets.QLabel("Players refreshed: …")
    owner.lblPlayerSnapshotTs.setWordWrap(True)
    owner.lblPlayerErrors = QtWidgets.QLabel("")
    owner.lblPlayerErrors.setWordWrap(True)
    owner.lblPlayerErrors.setStyleSheet("color:#E74C3C;")
    playerLay.addWidget(owner.lblAdminList)
    playerLay.addWidget(owner.lblPlayerSnapshotTs)
    playerLay.addWidget(owner.lblPlayerErrors)
    owner.playerTree = QtWidgets.QTreeWidget()
    owner.playerTree.setHeaderLabels(["Player / Character", "ID", "Details"])
    owner.playerTree.setRootIsDecorated(True)
    owner.playerTree.setUniformRowHeights(True)
    owner.playerTree.setColumnWidth(0, 220)
    owner.playerTree.setMinimumHeight(200)
    owner.playerTree.itemDoubleClicked.connect(
        lambda item, column: handle_player_tree_double_click(owner, item, column)
    )
    playerLay.addWidget(owner.playerTree, 1)
    owner.lblPlayerHint = QtWidgets.QLabel(
        "Double-click a player or character for full details."
    )
    owner.lblPlayerHint.setStyleSheet("font-style: italic; color:#95A5A6;")
    playerLay.addWidget(owner.lblPlayerHint)
    layout.addWidget(playerCard)

    bkCard = QtWidgets.QGroupBox("Backups")
    bkLay = QtWidgets.QGridLayout(bkCard)
    owner.lblBkEnabled = QtWidgets.QLabel("—")
    owner.lblBkLast = QtWidgets.QLabel("—")
    owner.lblBkFile = QtWidgets.QLabel("—")
    owner.lblBkTotal = QtWidgets.QLabel("0")
    owner.lblBkCounts = QtWidgets.QLabel("—")
    owner.lblBkCounts.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    bkLay.addWidget(QtWidgets.QLabel("Enabled:"), 0, 0)
    bkLay.addWidget(owner.lblBkEnabled, 0, 1)
    bkLay.addWidget(QtWidgets.QLabel("Last:"), 1, 0)
    bkLay.addWidget(owner.lblBkLast, 1, 1)
    bkLay.addWidget(QtWidgets.QLabel("File:"), 2, 0)
    bkLay.addWidget(owner.lblBkFile, 2, 1)
    bkLay.addWidget(QtWidgets.QLabel("Total:"), 3, 0)
    bkLay.addWidget(owner.lblBkTotal, 3, 1)
    bkLay.addWidget(QtWidgets.QLabel("Per-reason:"), 4, 0)
    bkLay.addWidget(owner.lblBkCounts, 4, 1)
    row = QtWidgets.QHBoxLayout()
    owner.btnBkNow = QtWidgets.QPushButton("Backup Now")
    owner.btnBkOpen = QtWidgets.QPushButton("Open Folder")
    row.addWidget(owner.btnBkNow)
    row.addWidget(owner.btnBkOpen)
    row.addStretch(1)
    bkLay.addLayout(row, 5, 0, 1, 2)
    layout.addWidget(bkCard)

    owner.dashboardScroll.setWidget(content)
    outer.addWidget(owner.dashboardScroll)

    return dashboard
