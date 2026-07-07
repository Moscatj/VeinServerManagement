"""About dialog for Vein Manager."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets
import PySide6


def _about_lines(info: dict[str, Any]) -> list[str]:
    lines = [
        f"Version: {info.get('version', 'unknown')}",
        f"Commit: {info.get('commit', 'unknown')}",
        f"Mode: {info.get('mode', 'unknown')}",
        f"Python: {info.get('python', 'unknown')}",
        f"PySide6: {getattr(PySide6, '__version__', 'unknown')}",
        f"Qt: {QtCore.qVersion()}",
        f"OS: {info.get('os', 'unknown')}",
        f"License: {info.get('license', 'unknown')}",
        f"Repository: {info.get('repository', '')}",
        f"App root: {info.get('app_root', '')}",
    ]
    config = str(info.get("config") or "").strip()
    if config:
        lines.append(f"Config: {config}")
    return lines


def about_text(info: dict[str, Any]) -> str:
    title = str(info.get("suite") or info.get("name") or "Vein Server Manager")
    return title + "\n\n" + "\n".join(_about_lines(info))


def show_about_dialog(parent: QtWidgets.QWidget, info: dict[str, Any]) -> None:
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("About Vein Server Manager")
    dialog.setModal(True)
    dialog.setMinimumWidth(520)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 16, 18, 14)
    layout.setSpacing(12)

    header = QtWidgets.QHBoxLayout()
    icon = QtWidgets.QLabel()
    pixmap = parent.windowIcon().pixmap(40, 40) if parent else QtGui.QPixmap()
    if not pixmap.isNull():
        icon.setPixmap(pixmap)
    else:
        icon.setPixmap(dialog.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation).pixmap(40, 40))
    header.addWidget(icon, 0, QtCore.Qt.AlignTop)

    title_block = QtWidgets.QVBoxLayout()
    name = QtWidgets.QLabel(str(info.get("name") or "Vein Server Manager"))
    font = name.font()
    font.setPointSize(max(font.pointSize() + 4, 13))
    font.setBold(True)
    name.setFont(font)
    suite = QtWidgets.QLabel(str(info.get("suite") or ""))
    suite.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    title_block.addWidget(name)
    title_block.addWidget(suite)
    header.addLayout(title_block, 1)
    layout.addLayout(header)

    details = QtWidgets.QPlainTextEdit("\n".join(_about_lines(info)))
    details.setReadOnly(True)
    details.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
    details.setMinimumHeight(220)
    layout.addWidget(details)

    buttons = QtWidgets.QDialogButtonBox()
    copy_btn = buttons.addButton("Copy", QtWidgets.QDialogButtonBox.ActionRole)
    ok_btn = buttons.addButton(QtWidgets.QDialogButtonBox.Ok)
    ok_btn.setDefault(True)
    copy_btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(about_text(info)))
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)

    dialog.exec()
