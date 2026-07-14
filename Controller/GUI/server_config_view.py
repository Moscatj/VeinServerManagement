"""Read-only server Game.ini / Engine.ini preview view."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .design_system import InlineNotice, PAGE_MARGIN, SECTION_SPACING, PageHeader
from .preflight import load_config_for_preflight
from Tools.server_config_editor import (
    apply_server_config_edits,
    make_edit,
    preview_server_config_edits,
)
from Tools.server_config_preview import build_server_config_preview


class ServerConfigPreviewSignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class ServerConfigPreviewWorker(QtCore.QRunnable):
    def __init__(self, config_path: str | Path):
        super().__init__()
        self.config_path = Path(config_path)
        self.signals = ServerConfigPreviewSignals()

    def run(self) -> None:
        try:
            cfg = load_config_for_preflight(self.config_path)
            payload = build_server_config_preview(cfg)
            payload["error"] = ""
        except Exception as exc:
            payload = {
                "server_root": "",
                "game_ini": "",
                "engine_ini": "",
                "items": [],
                "missing_files": [],
                "error": str(exc),
            }
        self.signals.ready.emit(payload)


class ServerConfigEditSignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


def edit_values_from_text(text: str) -> str | list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    return lines


class ServerConfigEditWorker(QtCore.QRunnable):
    def __init__(
        self,
        config_path: str | Path,
        *,
        action: str,
        source: str,
        section: str,
        key: str,
        value_text: str,
    ):
        super().__init__()
        self.config_path = Path(config_path)
        self.action = action
        self.source = source
        self.section = section
        self.key = key
        self.value_text = value_text
        self.signals = ServerConfigEditSignals()

    def run(self) -> None:
        try:
            cfg = load_config_for_preflight(self.config_path)
            edit = make_edit(
                self.source,
                self.section,
                self.key,
                edit_values_from_text(self.value_text),
            )
            if self.action == "apply":
                result = apply_server_config_edits(cfg, [edit])
                payload = result.as_dict()
            else:
                result = preview_server_config_edits(cfg, [edit])
                payload = result.as_dict()
            payload.update({"ok": True, "action": self.action, "error": ""})
        except Exception as exc:
            payload = {
                "ok": False,
                "action": self.action,
                "error": str(exc),
                "diffs": {},
                "changed_files": [],
                "backups": [],
                "validation": [],
            }
        self.signals.ready.emit(payload)


def build_server_config_preview_view(owner) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.addWidget(
        PageHeader(
            "Server Settings",
            "Review and safely edit supported VEIN Game.ini and Engine.ini settings.",
        )
    )
    layout.addWidget(
        InlineNotice(
            "The DiscordChatWebhookURL and DiscordChatAdminWebhookURL settings "
            "belong to VEIN and control game chat/admin reports. App startup, "
            "shutdown, crash, backup, and player notifications use the separate "
            "App notifications webhook on the Setup page."
        )
    )

    header = QtWidgets.QHBoxLayout()
    owner.lblServerConfigPreviewStatus = QtWidgets.QLabel("Refresh to inspect Game.ini and Engine.ini.")
    owner.lblServerConfigPreviewStatus.setWordWrap(True)
    owner.lblServerConfigPreviewStatus.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    owner.btnServerConfigPreviewRefresh = QtWidgets.QPushButton("Refresh")
    header.addWidget(owner.lblServerConfigPreviewStatus, 1)
    header.addWidget(owner.btnServerConfigPreviewRefresh)
    layout.addLayout(header)

    owner.treeServerConfigPreview = QtWidgets.QTreeWidget()
    owner.treeServerConfigPreview.setColumnCount(5)
    owner.treeServerConfigPreview.setHeaderLabels(["File", "Section", "Key", "Value", "State"])
    owner.treeServerConfigPreview.setRootIsDecorated(False)
    owner.treeServerConfigPreview.setAlternatingRowColors(True)
    owner.treeServerConfigPreview.setSortingEnabled(True)
    owner.treeServerConfigPreview.setTextElideMode(QtCore.Qt.ElideMiddle)
    owner.treeServerConfigPreview.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    layout.addWidget(owner.treeServerConfigPreview, 1)

    edit_group = QtWidgets.QGroupBox("Edit Selected Setting")
    edit_layout = QtWidgets.QVBoxLayout(edit_group)
    owner.lblServerConfigEditTarget = QtWidgets.QLabel("Select a setting to edit.")
    owner.lblServerConfigEditTarget.setWordWrap(True)
    owner.txtServerConfigEditValue = QtWidgets.QPlainTextEdit()
    owner.txtServerConfigEditValue.setPlaceholderText("Enter the proposed value. Use one line per value for admin/whitelist lists.")
    owner.txtServerConfigEditValue.setMaximumHeight(96)
    owner.txtServerConfigEditDiff = QtWidgets.QPlainTextEdit()
    owner.txtServerConfigEditDiff.setReadOnly(True)
    owner.txtServerConfigEditDiff.setPlaceholderText("Preview diff appears here before applying.")
    owner.txtServerConfigEditDiff.setMinimumHeight(120)
    buttons = QtWidgets.QHBoxLayout()
    owner.btnServerConfigEditPreview = QtWidgets.QPushButton("Preview Diff")
    owner.btnServerConfigEditApply = QtWidgets.QPushButton("Apply Change")
    owner.btnServerConfigEditApply.setEnabled(False)
    buttons.addWidget(owner.btnServerConfigEditPreview)
    buttons.addWidget(owner.btnServerConfigEditApply)
    buttons.addStretch(1)
    edit_layout.addWidget(owner.lblServerConfigEditTarget)
    edit_layout.addWidget(owner.txtServerConfigEditValue)
    edit_layout.addLayout(buttons)
    edit_layout.addWidget(owner.txtServerConfigEditDiff)
    layout.addWidget(edit_group)

    return widget
