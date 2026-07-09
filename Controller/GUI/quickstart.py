"""Preview-only Server Quick Start view."""

from __future__ import annotations

import json
from typing import Any

from PySide6 import QtWidgets

from Tools.server_quickstart import QuickStartPlan, build_quick_start_plan


def _line_edit(text: str = "") -> QtWidgets.QLineEdit:
    field = QtWidgets.QLineEdit()
    field.setText(text)
    return field


def _spin(value: int, minimum: int = 1, maximum: int = 65535) -> QtWidgets.QSpinBox:
    field = QtWidgets.QSpinBox()
    field.setRange(minimum, maximum)
    field.setValue(value)
    return field


def _plain_text(placeholder: str = "") -> QtWidgets.QPlainTextEdit:
    field = QtWidgets.QPlainTextEdit()
    field.setPlaceholderText(placeholder)
    field.setMaximumHeight(72)
    return field


def _add_row(layout: QtWidgets.QGridLayout, row: int, label: str, widget: QtWidgets.QWidget) -> None:
    layout.addWidget(QtWidgets.QLabel(label), row, 0)
    layout.addWidget(widget, row, 1)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def collect_quick_start_values(owner) -> dict[str, Any]:
    return {
        "server_name": owner.edQuickServerName.text(),
        "server_description": owner.txtQuickServerDescription.toPlainText(),
        "server_root": owner.edQuickServerRoot.text(),
        "steamcmd_path": owner.edQuickSteamCmd.text(),
        "max_players": owner.spinQuickMaxPlayers.value(),
        "game_port": owner.spinQuickGamePort.value(),
        "query_port": owner.spinQuickQueryPort.value(),
        "http_port": owner.spinQuickHttpPort.value(),
        "http_api_enabled": owner.chkQuickHttpApi.isChecked(),
        "public": owner.chkQuickPublic.isChecked(),
        "pvp_enabled": owner.chkQuickPvp.isChecked(),
        "vac_enabled": owner.chkQuickVac.isChecked(),
        "show_scoreboard_badges": owner.chkQuickScoreboardBadges.isChecked(),
        "bind_addr": owner.edQuickBindAddr.text(),
        "password": owner.edQuickPassword.text(),
        "admin_steam_ids": _lines(owner.txtQuickAdmins.toPlainText()),
        "super_admin_steam_ids": _lines(owner.txtQuickSuperAdmins.toPlainText()),
        "whitelisted_players": _lines(owner.txtQuickWhitelist.toPlainText()),
        "discord_chat_webhook_url": owner.edQuickDiscordChatWebhook.text(),
        "discord_chat_admin_webhook_url": owner.edQuickDiscordAdminWebhook.text(),
    }


def format_quick_start_plan(plan: QuickStartPlan) -> str:
    lines: list[str] = []
    lines.append("Server Quick Start Preview")
    lines.append("")
    lines.append(f"Can apply: {'yes' if plan.can_apply else 'no'}")
    lines.append("")
    lines.append("Issues:")
    if plan.issues:
        for issue in plan.issues:
            lines.append(f"- {issue.severity} {issue.field}: {issue.message}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Management config updates:")
    lines.append(json.dumps(plan.config_updates, indent=2, sort_keys=True))
    lines.append("")
    lines.append("Game config edits:")
    for edit in plan.server_config_edits:
        value = ", ".join(edit.values)
        lines.append(f"- {edit.source} [{edit.section}] {edit.key} = {value}")
    return "\n".join(lines)


def build_quick_start_view(owner) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    owner.lblQuickStartStatus = QtWidgets.QLabel(
        "Fill in first-run server settings, then build a preview. This view does not write files yet."
    )
    owner.lblQuickStartStatus.setWordWrap(True)
    layout.addWidget(owner.lblQuickStartStatus)

    form = QtWidgets.QGroupBox("Server Quick Start")
    grid = QtWidgets.QGridLayout(form)
    grid.setColumnStretch(1, 1)

    owner.edQuickServerName = _line_edit()
    owner.txtQuickServerDescription = _plain_text("Server rules, gameplay style, or MOTD.")
    owner.edQuickServerRoot = _line_edit("Server")
    owner.edQuickSteamCmd = _line_edit("SteamCMD/steamcmd.exe")
    owner.spinQuickMaxPlayers = _spin(8, 1, 200)
    owner.spinQuickGamePort = _spin(7777)
    owner.spinQuickQueryPort = _spin(27015)
    owner.spinQuickHttpPort = _spin(8080)
    owner.edQuickBindAddr = _line_edit("0.0.0.0")
    owner.edQuickPassword = _line_edit()
    owner.edQuickPassword.setEchoMode(QtWidgets.QLineEdit.Password)

    owner.chkQuickPublic = QtWidgets.QCheckBox("List server publicly")
    owner.chkQuickPublic.setChecked(True)
    owner.chkQuickHttpApi = QtWidgets.QCheckBox("Enable local HTTP API")
    owner.chkQuickHttpApi.setChecked(True)
    owner.chkQuickPvp = QtWidgets.QCheckBox("Enable PvP")
    owner.chkQuickPvp.setChecked(True)
    owner.chkQuickVac = QtWidgets.QCheckBox("Enable VAC")
    owner.chkQuickScoreboardBadges = QtWidgets.QCheckBox("Show admin scoreboard badges")
    owner.chkQuickScoreboardBadges.setChecked(True)

    owner.txtQuickAdmins = _plain_text("One SteamID64 per line.")
    owner.txtQuickSuperAdmins = _plain_text("One SteamID64 per line.")
    owner.txtQuickWhitelist = _plain_text("Optional. One SteamID64 per line.")
    owner.edQuickDiscordChatWebhook = _line_edit()
    owner.edQuickDiscordAdminWebhook = _line_edit()

    row = 0
    for label, field in [
        ("Server name", owner.edQuickServerName),
        ("Description", owner.txtQuickServerDescription),
        ("Server root", owner.edQuickServerRoot),
        ("SteamCMD", owner.edQuickSteamCmd),
        ("Max players", owner.spinQuickMaxPlayers),
        ("Gameplay port", owner.spinQuickGamePort),
        ("Steam query port", owner.spinQuickQueryPort),
        ("HTTP API port", owner.spinQuickHttpPort),
        ("Bind address", owner.edQuickBindAddr),
        ("Password", owner.edQuickPassword),
    ]:
        _add_row(grid, row, label, field)
        row += 1

    toggles = QtWidgets.QHBoxLayout()
    for checkbox in [
        owner.chkQuickPublic,
        owner.chkQuickHttpApi,
        owner.chkQuickPvp,
        owner.chkQuickVac,
        owner.chkQuickScoreboardBadges,
    ]:
        toggles.addWidget(checkbox)
    toggles.addStretch(1)
    grid.addLayout(toggles, row, 0, 1, 2)
    row += 1

    for label, field in [
        ("Admin Steam IDs", owner.txtQuickAdmins),
        ("Super admin Steam IDs", owner.txtQuickSuperAdmins),
        ("Whitelist Steam IDs", owner.txtQuickWhitelist),
        ("Discord chat webhook", owner.edQuickDiscordChatWebhook),
        ("Discord admin webhook", owner.edQuickDiscordAdminWebhook),
    ]:
        _add_row(grid, row, label, field)
        row += 1

    layout.addWidget(form)

    actions = QtWidgets.QHBoxLayout()
    owner.btnQuickStartPreview = QtWidgets.QPushButton("Build Preview")
    actions.addWidget(owner.btnQuickStartPreview)
    actions.addStretch(1)
    layout.addLayout(actions)

    owner.txtQuickStartPreview = QtWidgets.QPlainTextEdit()
    owner.txtQuickStartPreview.setReadOnly(True)
    owner.txtQuickStartPreview.setPlaceholderText("Generated setup preview appears here.")
    layout.addWidget(owner.txtQuickStartPreview, 1)

    return widget


def build_quick_start_preview(owner) -> str:
    plan = build_quick_start_plan(collect_quick_start_values(owner))
    return format_quick_start_plan(plan)
