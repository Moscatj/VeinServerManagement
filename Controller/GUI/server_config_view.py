"""Read-only server Game.ini / Engine.ini preview view."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .preflight import load_config_for_preflight
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


def build_server_config_preview_view(owner) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

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
    owner.treeServerConfigPreview.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
    layout.addWidget(owner.treeServerConfigPreview, 1)

    return widget
