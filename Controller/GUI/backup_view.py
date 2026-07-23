"""Read-only backup history view and background archive discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from PySide6 import QtCore, QtWidgets

from Tools.backups import list_backup_archives
from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    InlineNotice,
    PAGE_MARGIN,
    SECTION_SPACING,
    PageHeader,
    set_button_role,
)


def format_archive_size(size_bytes: int) -> str:
    """Format archive bytes for a compact history table."""
    size = max(0, int(size_bytes))
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class BackupHistorySignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class BackupHistoryWorker(QtCore.QRunnable):
    """Scan a configured backup root without blocking the GUI thread."""

    def __init__(self, root: str | Path, *, limit: int = 200) -> None:
        super().__init__()
        self.root = Path(root)
        self.limit = limit
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            archives = list_backup_archives(self.root, limit=self.limit)
            payload = {
                "ok": True,
                "root": str(self.root),
                "archives": [archive.as_dict() for archive in archives],
                "error": "",
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "root": str(self.root),
                "archives": [],
                "error": str(exc),
            }
        self.signals.ready.emit(payload)


def populate_backup_history(owner, payload: Mapping[str, Any]) -> None:
    """Render a backup history payload without performing filesystem work."""
    tree = owner.treeBackupHistory
    tree.clear()
    archives: Sequence[Mapping[str, Any]] = payload.get("archives") or []
    error = str(payload.get("error") or "")
    root = str(payload.get("root") or "")
    if error:
        owner.lblBackupHistoryStatus.setText(f"Backup history could not be loaded: {error}")
        owner.lblBackupHistoryStatus.set_kind("error")
    elif archives:
        owner.lblBackupHistoryStatus.setText(
            f"Showing {len(archives)} newest archive(s) under {root}."
        )
        owner.lblBackupHistoryStatus.set_kind("success")
    else:
        owner.lblBackupHistoryStatus.setText(
            f"No backup archives were found under {root}."
        )
        owner.lblBackupHistoryStatus.set_kind("warning")

    for archive in archives:
        path = str(archive.get("path") or "")
        item = QtWidgets.QTreeWidgetItem(
            [
                str(archive.get("modified") or ""),
                str(archive.get("category") or ""),
                str(archive.get("filename") or ""),
                format_archive_size(int(archive.get("size_bytes") or 0)),
            ]
        )
        item.setData(0, QtCore.Qt.UserRole, path)
        item.setToolTip(2, path)
        tree.addTopLevelItem(item)
    for column in range(tree.columnCount()):
        tree.resizeColumnToContents(column)
    owner.lblBackupHistoryPath.setText(
        "Select an archive to inspect its full path." if archives else ""
    )


def build_backup_history_view(owner) -> QtWidgets.QWidget:
    """Build the dedicated read-only Backups page."""
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.addWidget(
        PageHeader(
            "Backups",
            "Review save, log, and configuration archives without modifying them.",
        )
    )
    layout.addWidget(
        InlineNotice(
            "Archive browsing is read-only. Backup Now uses the same safe manual-backup "
            "workflow as Home. Loading a save is not offered until it can preview the "
            "destination, protect the current save, and validate the result."
        )
    )

    controls = QtWidgets.QHBoxLayout()
    owner.btnBackupHistoryRefresh = QtWidgets.QPushButton("Refresh")
    owner.btnBackupHistoryOpen = QtWidgets.QPushButton("Open Backups Folder")
    owner.btnBackupHistoryCreate = QtWidgets.QPushButton("Backup Now")
    set_button_role(owner.btnBackupHistoryRefresh, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryOpen, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryCreate, BUTTON_PRIMARY)
    controls.addWidget(owner.btnBackupHistoryRefresh)
    controls.addWidget(owner.btnBackupHistoryOpen)
    controls.addStretch(1)
    controls.addWidget(owner.btnBackupHistoryCreate)
    layout.addLayout(controls)

    owner.lblBackupHistoryStatus = InlineNotice("Loading backup history.")
    layout.addWidget(owner.lblBackupHistoryStatus)

    owner.treeBackupHistory = QtWidgets.QTreeWidget()
    owner.treeBackupHistory.setColumnCount(4)
    owner.treeBackupHistory.setHeaderLabels(["Created", "Category", "Archive", "Size"])
    owner.treeBackupHistory.setRootIsDecorated(False)
    owner.treeBackupHistory.setAlternatingRowColors(True)
    owner.treeBackupHistory.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    owner.treeBackupHistory.setSortingEnabled(False)
    layout.addWidget(owner.treeBackupHistory, 1)

    owner.lblBackupHistoryPath = QtWidgets.QLabel()
    owner.lblBackupHistoryPath.setWordWrap(True)
    owner.lblBackupHistoryPath.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    layout.addWidget(owner.lblBackupHistoryPath)

    owner.treeBackupHistory.currentItemChanged.connect(
        lambda current, _previous: owner.lblBackupHistoryPath.setText(
            str(current.data(0, QtCore.Qt.UserRole)) if current else ""
        )
    )
    owner.btnBackupHistoryRefresh.clicked.connect(
        getattr(owner, "_refresh_backup_history", lambda: None)
    )
    owner.btnBackupHistoryOpen.clicked.connect(
        getattr(owner, "_on_open_backups_clicked", lambda: None)
    )
    owner.btnBackupHistoryCreate.clicked.connect(
        getattr(owner, "_on_backup_now_clicked", lambda: None)
    )
    return widget
