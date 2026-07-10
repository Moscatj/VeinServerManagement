"""Server Quick Start view and existing-install loader."""

from __future__ import annotations

import json
from typing import Any

from PySide6 import QtCore, QtWidgets

from Tools.server_config_preview import mask_config_value
from Tools.server_quickstart import (
    EXISTING_SERVER_MODE,
    NEW_SERVER_MODE,
    ExistingServerSettings,
    QuickStartApplyResult,
    QuickStartPlan,
    ServerRootInspection,
    apply_quick_start_plan,
    build_quick_start_plan,
    load_existing_server_settings,
)
from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    PAGE_MARGIN,
    SECTION_SPACING,
    InlineNotice,
    PageHeader,
    set_button_role,
)


class ExistingServerLoadSignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class ExistingServerLoadWorker(QtCore.QRunnable):
    def __init__(self, server_root: str, executables: list[str] | None = None):
        super().__init__()
        self.server_root = server_root
        self.executables = executables
        self.signals = ExistingServerLoadSignals()

    def run(self) -> None:
        try:
            settings = load_existing_server_settings(self.server_root, self.executables)
            payload = {"ok": True, "error": "", **settings.as_dict()}
        except Exception as exc:
            payload = {"ok": False, "error": str(exc)}
        self.signals.ready.emit(payload)


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


def _add_path_row(
    layout: QtWidgets.QGridLayout,
    row: int,
    label: str,
    field: QtWidgets.QLineEdit,
    browse_button: QtWidgets.QPushButton,
) -> None:
    path_widget = QtWidgets.QWidget()
    path_layout = QtWidgets.QHBoxLayout(path_widget)
    path_layout.setContentsMargins(0, 0, 0, 0)
    path_layout.addWidget(field, 1)
    path_layout.addWidget(browse_button)
    _add_row(layout, row, label, path_widget)


def set_quick_start_password_visibility(owner, visible: bool) -> None:
    owner.edQuickPassword.setEchoMode(
        QtWidgets.QLineEdit.Normal if visible else QtWidgets.QLineEdit.Password
    )
    owner.btnQuickPasswordVisibility.setText("Hide" if visible else "Show")


def update_quick_start_password_status(owner) -> None:
    if owner.edQuickPassword.text():
        text = "Password status: replacement password entered."
    elif owner.cmbQuickSetupMode.currentData() == NEW_SERVER_MODE:
        text = "Password status: no password will be set."
    else:
        configured = getattr(owner, "_quick_start_existing_password_configured", None)
        if configured is True:
            text = "Password status: existing password is set and will be preserved."
        elif configured is False:
            text = "Password status: no existing password is set."
        else:
            text = "Password status: unknown until existing settings are loaded."
    owner.lblQuickPasswordStatus.setText(text)


def set_quick_start_webhook_visibility(
    field: QtWidgets.QLineEdit,
    button: QtWidgets.QPushButton,
    visible: bool,
) -> None:
    field.setEchoMode(QtWidgets.QLineEdit.Normal if visible else QtWidgets.QLineEdit.Password)
    button.setText("Hide" if visible else "Show")


def _webhook_status_text(label: str, replacement: str, configured: bool | None, mode: str) -> str:
    if replacement:
        return f"{label} status: replacement URL entered."
    if mode == NEW_SERVER_MODE:
        return f"{label} status: no webhook will be set."
    if configured is True:
        return f"{label} status: existing webhook is configured and will be preserved."
    if configured is False:
        return f"{label} status: no existing webhook is configured."
    return f"{label} status: unknown until existing settings are loaded."


def update_quick_start_webhook_statuses(owner) -> None:
    mode = owner.cmbQuickSetupMode.currentData()
    owner.lblQuickDiscordChatWebhookStatus.setText(
        _webhook_status_text(
            "Chat webhook",
            owner.edQuickDiscordChatWebhook.text(),
            getattr(owner, "_quick_start_existing_chat_webhook_configured", None),
            mode,
        )
    )
    owner.lblQuickDiscordAdminWebhookStatus.setText(
        _webhook_status_text(
            "Admin webhook",
            owner.edQuickDiscordAdminWebhook.text(),
            getattr(owner, "_quick_start_existing_admin_webhook_configured", None),
            mode,
        )
    )


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def collect_quick_start_values(owner) -> dict[str, Any]:
    return {
        "setup_mode": owner.cmbQuickSetupMode.currentData(),
        "server_config_fields": sorted(getattr(owner, "_quick_start_dirty_fields", set())),
        "existing_loaded_root": getattr(owner, "_quick_start_existing_loaded_root", ""),
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
    if not plan.server_config_edits:
        lines.append("- none; existing game settings will be preserved")
    for edit in plan.server_config_edits:
        value = ", ".join(mask_config_value(edit.key, item) for item in edit.values)
        lines.append(f"- {edit.source} [{edit.section}] {edit.key} = {value}")
    return "\n".join(lines)


def format_quick_start_apply_result(result: QuickStartApplyResult) -> str:
    lines = [format_quick_start_plan(result.plan), "", "Apply result:"]
    lines.append(f"- Management config: {'updated' if result.config_changed else 'already current'}")
    lines.append(f"- Config path: {result.config_path}")
    lines.append(f"- Config backup: {result.config_backup}")
    lines.append(
        f"- Game config: {'applied' if result.server_config_applied else 'not applied'}"
    )
    for message in result.messages:
        lines.append(f"- {message}")
    server_result = result.server_config_result or {}
    backups = server_result.get("backups") or []
    if backups:
        lines.append("- Game config backup(s):")
        for backup in backups:
            lines.append(f"  {backup}")
    return "\n".join(lines)


def quick_start_config_path(owner) -> str | None:
    path = getattr(owner, "config_path", "") or ""
    name = str(path).lower()
    if not path or "example" in name or ".sample" in name:
        return None
    return path


def build_quick_start_view(owner) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)

    layout.addWidget(
        PageHeader(
            "Quick Start",
            "Configure a new server or safely import and update an existing installation.",
        )
    )

    owner._quick_start_dirty_fields = set()
    owner._quick_start_loading_existing = False
    owner._quick_start_existing_loaded_root = ""
    owner.lblQuickStartStatus = InlineNotice(
        "Choose whether to configure a new or existing server."
    )
    layout.addWidget(owner.lblQuickStartStatus)

    form = QtWidgets.QGroupBox("Server Quick Start")
    grid = QtWidgets.QGridLayout(form)
    grid.setColumnStretch(1, 1)

    owner.cmbQuickSetupMode = QtWidgets.QComboBox()
    owner.cmbQuickSetupMode.addItem("New Server", NEW_SERVER_MODE)
    owner.cmbQuickSetupMode.addItem("Existing Server", EXISTING_SERVER_MODE)

    owner.edQuickServerName = _line_edit()
    owner.txtQuickServerDescription = _plain_text("Server rules, gameplay style, or MOTD.")
    owner.edQuickServerRoot = _line_edit("Server")
    owner.edQuickSteamCmd = _line_edit("SteamCMD/steamcmd.exe")
    owner.btnQuickStartBrowseRoot = QtWidgets.QPushButton("Browse…")
    owner.btnQuickStartBrowseRoot.setToolTip("Select the Vein dedicated server folder")
    owner.btnQuickStartBrowseSteamCmd = QtWidgets.QPushButton("Browse…")
    owner.btnQuickStartBrowseSteamCmd.setToolTip("Select steamcmd.exe")
    owner.spinQuickMaxPlayers = _spin(8, 1, 200)
    owner.spinQuickGamePort = _spin(7777)
    owner.spinQuickQueryPort = _spin(27015)
    owner.spinQuickHttpPort = _spin(8080)
    owner.edQuickBindAddr = _line_edit("0.0.0.0")
    owner.edQuickPassword = _line_edit()
    owner.edQuickPassword.setEchoMode(QtWidgets.QLineEdit.Password)
    owner.edQuickPassword.setPlaceholderText("Leave blank to preserve an existing password")
    owner.btnQuickPasswordVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickPasswordVisibility.setCheckable(True)
    owner.btnQuickPasswordVisibility.setToolTip("Show or hide the replacement password entered here")
    owner.lblQuickPasswordStatus = QtWidgets.QLabel()
    owner.lblQuickPasswordStatus.setWordWrap(True)

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
    for field in (owner.edQuickDiscordChatWebhook, owner.edQuickDiscordAdminWebhook):
        field.setEchoMode(QtWidgets.QLineEdit.Password)
        field.setPlaceholderText("Leave blank to preserve an existing webhook")
    owner.btnQuickDiscordChatWebhookVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickDiscordChatWebhookVisibility.setCheckable(True)
    owner.btnQuickDiscordAdminWebhookVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickDiscordAdminWebhookVisibility.setCheckable(True)
    owner.lblQuickDiscordChatWebhookStatus = QtWidgets.QLabel()
    owner.lblQuickDiscordAdminWebhookStatus = QtWidgets.QLabel()
    owner.lblQuickDiscordChatWebhookStatus.setWordWrap(True)
    owner.lblQuickDiscordAdminWebhookStatus.setWordWrap(True)

    row = 0
    _add_row(grid, row, "Setup mode", owner.cmbQuickSetupMode)
    row += 1
    for label, field in [
        ("Server name", owner.edQuickServerName),
        ("Description", owner.txtQuickServerDescription),
    ]:
        _add_row(grid, row, label, field)
        row += 1
    _add_path_row(grid, row, "Server root", owner.edQuickServerRoot, owner.btnQuickStartBrowseRoot)
    row += 1
    _add_path_row(grid, row, "SteamCMD", owner.edQuickSteamCmd, owner.btnQuickStartBrowseSteamCmd)
    row += 1
    for label, field in [
        ("Max players", owner.spinQuickMaxPlayers),
        ("Gameplay port", owner.spinQuickGamePort),
        ("Steam query port", owner.spinQuickQueryPort),
        ("HTTP API port", owner.spinQuickHttpPort),
        ("Bind address", owner.edQuickBindAddr),
    ]:
        _add_row(grid, row, label, field)
        row += 1
    _add_path_row(grid, row, "Password", owner.edQuickPassword, owner.btnQuickPasswordVisibility)
    row += 1
    grid.addWidget(owner.lblQuickPasswordStatus, row, 1)
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
    ]:
        _add_row(grid, row, label, field)
        row += 1
    _add_path_row(
        grid,
        row,
        "Discord chat webhook",
        owner.edQuickDiscordChatWebhook,
        owner.btnQuickDiscordChatWebhookVisibility,
    )
    row += 1
    grid.addWidget(owner.lblQuickDiscordChatWebhookStatus, row, 1)
    row += 1
    _add_path_row(
        grid,
        row,
        "Discord admin webhook",
        owner.edQuickDiscordAdminWebhook,
        owner.btnQuickDiscordAdminWebhookVisibility,
    )
    row += 1
    grid.addWidget(owner.lblQuickDiscordAdminWebhookStatus, row, 1)
    row += 1

    layout.addWidget(form)

    actions = QtWidgets.QHBoxLayout()
    owner.btnQuickStartLoadExisting = QtWidgets.QPushButton("Load Existing Settings")
    owner.btnQuickStartLoadExisting.setEnabled(False)
    owner.btnQuickStartPreview = QtWidgets.QPushButton("Build Preview")
    owner.btnQuickStartApply = QtWidgets.QPushButton("Apply Setup")
    owner.btnQuickStartApply.setEnabled(False)
    set_button_role(owner.btnQuickStartLoadExisting, BUTTON_SECONDARY)
    set_button_role(owner.btnQuickStartPreview, BUTTON_SECONDARY)
    set_button_role(owner.btnQuickStartApply, BUTTON_PRIMARY)
    actions.addWidget(owner.btnQuickStartLoadExisting)
    actions.addWidget(owner.btnQuickStartPreview)
    actions.addWidget(owner.btnQuickStartApply)
    actions.addStretch(1)
    layout.addLayout(actions)

    owner.txtQuickStartPreview = QtWidgets.QPlainTextEdit()
    owner.txtQuickStartPreview.setReadOnly(True)
    owner.txtQuickStartPreview.setPlaceholderText("Generated setup preview appears here.")
    layout.addWidget(owner.txtQuickStartPreview, 1)

    tracked_widgets = {
        "server_name": owner.edQuickServerName,
        "server_description": owner.txtQuickServerDescription,
        "max_players": owner.spinQuickMaxPlayers,
        "game_port": owner.spinQuickGamePort,
        "query_port": owner.spinQuickQueryPort,
        "http_port": owner.spinQuickHttpPort,
        "bind_addr": owner.edQuickBindAddr,
        "password": owner.edQuickPassword,
        "public": owner.chkQuickPublic,
        "http_api_enabled": owner.chkQuickHttpApi,
        "pvp_enabled": owner.chkQuickPvp,
        "vac_enabled": owner.chkQuickVac,
        "show_scoreboard_badges": owner.chkQuickScoreboardBadges,
        "admin_steam_ids": owner.txtQuickAdmins,
        "super_admin_steam_ids": owner.txtQuickSuperAdmins,
        "whitelisted_players": owner.txtQuickWhitelist,
        "discord_chat_webhook_url": owner.edQuickDiscordChatWebhook,
        "discord_chat_admin_webhook_url": owner.edQuickDiscordAdminWebhook,
    }
    owner._quick_start_tracked_widgets = tracked_widgets
    for field, tracked in tracked_widgets.items():
        signal = getattr(tracked, "textChanged", None) or getattr(tracked, "valueChanged", None) or tracked.toggled
        signal.connect(lambda *_, field=field: mark_quick_start_field_changed(owner, field))
    owner.edQuickServerRoot.textChanged.connect(lambda: invalidate_existing_quick_start_load(owner))
    owner.edQuickPassword.textChanged.connect(lambda: update_quick_start_password_status(owner))
    owner.btnQuickPasswordVisibility.toggled.connect(
        lambda checked: set_quick_start_password_visibility(owner, checked)
    )
    owner.edQuickDiscordChatWebhook.textChanged.connect(
        lambda: update_quick_start_webhook_statuses(owner)
    )
    owner.edQuickDiscordAdminWebhook.textChanged.connect(
        lambda: update_quick_start_webhook_statuses(owner)
    )
    owner.btnQuickDiscordChatWebhookVisibility.toggled.connect(
        lambda checked: set_quick_start_webhook_visibility(
            owner.edQuickDiscordChatWebhook,
            owner.btnQuickDiscordChatWebhookVisibility,
            checked,
        )
    )
    owner.btnQuickDiscordAdminWebhookVisibility.toggled.connect(
        lambda checked: set_quick_start_webhook_visibility(
            owner.edQuickDiscordAdminWebhook,
            owner.btnQuickDiscordAdminWebhookVisibility,
            checked,
        )
    )
    update_quick_start_password_status(owner)
    update_quick_start_webhook_statuses(owner)

    return widget


def mark_quick_start_field_changed(owner, field: str) -> None:
    if getattr(owner, "_quick_start_loading_existing", False):
        return
    if owner.cmbQuickSetupMode.currentData() == EXISTING_SERVER_MODE:
        owner._quick_start_dirty_fields.add(field)
    owner.btnQuickStartApply.setEnabled(False)


def set_quick_start_mode(owner, mode: str) -> None:
    existing = mode == EXISTING_SERVER_MODE
    owner._quick_start_dirty_fields.clear()
    owner._quick_start_existing_loaded_root = ""
    owner._quick_start_existing_password_configured = None
    owner._quick_start_existing_chat_webhook_configured = None
    owner._quick_start_existing_admin_webhook_configured = None
    owner.btnQuickStartLoadExisting.setEnabled(existing)
    owner.btnQuickStartApply.setEnabled(False)
    owner.lblQuickStartStatus.setText(
        "Select the installed server folder, then load its current settings before editing."
        if existing
        else "Enter settings for a new server, then build and review the complete preview."
    )
    owner.lblQuickStartStatus.set_kind("info")
    update_quick_start_password_status(owner)
    update_quick_start_webhook_statuses(owner)


def enforce_quick_start_root_mode(owner, inspection: ServerRootInspection) -> bool:
    """Force detected Vein installations into Existing Server mode."""
    if not inspection.is_existing_server:
        return False

    owner._quick_start_auto_detected_root = inspection.server_root
    index = owner.cmbQuickSetupMode.findData(EXISTING_SERVER_MODE)
    if index >= 0 and owner.cmbQuickSetupMode.currentIndex() != index:
        owner.cmbQuickSetupMode.setCurrentIndex(index)
    owner.lblQuickStartStatus.setText(
        "Existing Vein server files were detected. Existing Server mode is required and current settings are being loaded."
    )
    owner.lblQuickStartStatus.set_kind("warning")
    return True


def populate_existing_server_settings(owner, settings: ExistingServerSettings) -> None:
    owner._quick_start_loading_existing = True
    try:
        values = settings.values
        owner.edQuickServerRoot.setText(settings.server_root)
        setters = {
            "server_name": owner.edQuickServerName.setText,
            "server_description": owner.txtQuickServerDescription.setPlainText,
            "max_players": owner.spinQuickMaxPlayers.setValue,
            "game_port": owner.spinQuickGamePort.setValue,
            "query_port": owner.spinQuickQueryPort.setValue,
            "http_port": owner.spinQuickHttpPort.setValue,
            "bind_addr": owner.edQuickBindAddr.setText,
            "public": owner.chkQuickPublic.setChecked,
            "pvp_enabled": owner.chkQuickPvp.setChecked,
            "vac_enabled": owner.chkQuickVac.setChecked,
            "show_scoreboard_badges": owner.chkQuickScoreboardBadges.setChecked,
            "admin_steam_ids": lambda value: owner.txtQuickAdmins.setPlainText("\n".join(value)),
            "super_admin_steam_ids": lambda value: owner.txtQuickSuperAdmins.setPlainText("\n".join(value)),
            "whitelisted_players": lambda value: owner.txtQuickWhitelist.setPlainText("\n".join(value)),
        }
        for field, setter in setters.items():
            if field in values:
                setter(values[field])
        owner.edQuickPassword.clear()
        owner.edQuickDiscordChatWebhook.clear()
        owner.edQuickDiscordAdminWebhook.clear()
    finally:
        owner._quick_start_loading_existing = False
    owner._quick_start_dirty_fields.clear()
    owner._quick_start_existing_loaded_root = settings.server_root
    owner._quick_start_existing_password_configured = settings.password_configured
    owner._quick_start_existing_chat_webhook_configured = settings.discord_chat_webhook_configured
    owner._quick_start_existing_admin_webhook_configured = settings.discord_admin_webhook_configured
    update_quick_start_password_status(owner)
    update_quick_start_webhook_statuses(owner)
    owner.lblQuickStartStatus.set_kind("success")
    owner.btnQuickStartApply.setEnabled(False)


def invalidate_existing_quick_start_load(owner) -> None:
    if getattr(owner, "_quick_start_loading_existing", False):
        return
    if owner.cmbQuickSetupMode.currentData() == EXISTING_SERVER_MODE:
        owner._quick_start_existing_loaded_root = ""
        owner._quick_start_existing_password_configured = None
        owner._quick_start_existing_chat_webhook_configured = None
        owner._quick_start_existing_admin_webhook_configured = None
        owner._quick_start_dirty_fields.clear()
        owner.btnQuickStartApply.setEnabled(False)
        update_quick_start_password_status(owner)
        update_quick_start_webhook_statuses(owner)


def build_quick_start_plan_from_owner(owner) -> QuickStartPlan:
    return build_quick_start_plan(collect_quick_start_values(owner))


def build_quick_start_preview(owner) -> str:
    plan = build_quick_start_plan_from_owner(owner)
    return format_quick_start_plan(plan)


def apply_quick_start(owner) -> str:
    result = apply_quick_start_plan(
        collect_quick_start_values(owner),
        config_path=quick_start_config_path(owner),
    )
    return format_quick_start_apply_result(result)
