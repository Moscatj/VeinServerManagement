"""Server Quick Start view and existing-install loader."""

from __future__ import annotations

import json
from pathlib import Path
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
    management_webhook_summary,
)
from Tools.setup_state import SetupAssessment, SetupMetadata, SetupState, SetupWorkflow
from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    PAGE_MARGIN,
    SECTION_SPACING,
    InlineNotice,
    PageHeader,
    set_button_role,
)


QUICK_START_STEPS = (
    ("Location", "Choose whether this is a new or existing server and confirm its local paths."),
    ("Identity & Access", "Set the server identity, player access, and gameplay safeguards."),
    ("Network & Integrations", "Review ports, local API exposure, and Discord destinations."),
    ("Review & Apply", "Build a masked preview before applying any configuration changes."),
)


def set_quick_start_step(owner, index: int) -> None:
    """Show one Quick Start page without recreating or clearing its widgets."""
    last = len(QUICK_START_STEPS) - 1
    current = max(0, min(int(index), last))
    owner.quickStartStack.setCurrentIndex(current)
    title, description = QUICK_START_STEPS[current]
    owner.lblQuickStartStep.setText(
        f"Step {current + 1} of {len(QUICK_START_STEPS)} — {title}\n{description}"
    )
    owner.btnQuickStartBack.setVisible(True)
    owner.btnQuickStartBack.setEnabled(current > 0)
    owner.btnQuickStartNext.setVisible(current < last)
    owner.btnQuickStartLoadExisting.setVisible(False)
    owner.btnQuickStartConnectExisting.setVisible(False)
    owner.btnQuickStartOpenSettings.setVisible(False)
    owner.btnQuickStartPreview.setVisible(current == last)
    owner.btnQuickStartApply.setVisible(current == last)


def _show_new_server_wizard(owner) -> None:
    owner._quick_start_compact_existing = False
    owner.lblQuickStartStep.setVisible(True)
    owner.btnQuickStartConnectExisting.setVisible(False)
    owner.btnQuickStartOpenSettings.setVisible(False)
    set_quick_start_step(owner, 0)


def _show_existing_server_actions(owner) -> None:
    owner._quick_start_compact_existing = True
    owner.quickStartStack.setCurrentIndex(0)
    owner.lblQuickStartStep.setVisible(False)
    owner.btnQuickStartBack.setVisible(False)
    owner.btnQuickStartNext.setVisible(False)
    owner.btnQuickStartPreview.setVisible(False)
    owner.btnQuickStartApply.setVisible(False)
    owner.btnQuickStartLoadExisting.setVisible(True)
    owner.btnQuickStartConnectExisting.setVisible(True)
    owner.btnQuickStartOpenSettings.setVisible(False)


def route_quick_start_workflow(
    owner,
    assessment: SetupAssessment,
    metadata: SetupMetadata | None = None,
) -> None:
    """Route Setup to a wizard, compact import, or everyday settings action."""
    owner._quick_start_setup_workflow = assessment.workflow.value
    owner._quick_start_setup_source = (metadata.source if metadata else "unconfigured")

    desired_mode = (
        EXISTING_SERVER_MODE
        if assessment.workflow == SetupWorkflow.EXISTING_SERVER
        else NEW_SERVER_MODE
    )
    index = owner.cmbQuickSetupMode.findData(desired_mode)
    if index >= 0:
        owner.cmbQuickSetupMode.blockSignals(True)
        owner.cmbQuickSetupMode.setCurrentIndex(index)
        owner.cmbQuickSetupMode.blockSignals(False)
    set_quick_start_mode(owner, desired_mode)

    if assessment.state == SetupState.CONFIGURED:
        owner.btnQuickStartLoadExisting.setVisible(False)
        owner.btnQuickStartConnectExisting.setVisible(False)
        owner.btnQuickStartOpenSettings.setVisible(True)
        owner.lblQuickStartStatus.setText(
            "This server is already configured. Use Server Settings for quick, guarded edits."
        )
        owner.lblQuickStartStatus.set_kind("success")
    else:
        owner.lblQuickStartStatus.setText(f"{assessment.primary_action}: {assessment.reason}")
        owner.lblQuickStartStatus.set_kind(
            "warning" if assessment.state in {SetupState.REPAIR_MISSING, SetupState.AMBIGUOUS} else "info"
        )


def move_quick_start_step(owner, offset: int) -> None:
    """Move within the bounded wizard while preserving the existing form state."""
    set_quick_start_step(owner, owner.quickStartStack.currentIndex() + int(offset))


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
    field.setMinimumHeight(28)
    return field


def _spin(value: int, minimum: int = 1, maximum: int = 65535) -> QtWidgets.QSpinBox:
    field = QtWidgets.QSpinBox()
    field.setRange(minimum, maximum)
    field.setValue(value)
    field.setMinimumHeight(28)
    return field


def _plain_text(placeholder: str = "") -> QtWidgets.QPlainTextEdit:
    field = QtWidgets.QPlainTextEdit()
    field.setPlaceholderText(placeholder)
    field.setMinimumHeight(64)
    field.setMaximumHeight(96)
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


def update_quick_start_game_log_path(owner) -> None:
    """Show the single game-log path that launch and monitoring will share."""
    automatic = (
        Path(owner.edQuickServerRoot.text().strip() or "Server")
        / "Vein"
        / "Saved"
        / "Logs"
        / "Vein.log"
    )
    override = owner.edQuickGameLogOverride.text().strip()
    use_override = owner.grpQuickGameLogOverride.isChecked() and bool(override)
    owner.edQuickGameLogResolved.setText(str(Path(override) if use_override else automatic))
    owner.lblQuickGameLogMode.setText(
        "Advanced override active. Vein launch and monitoring will both use this file."
        if use_override
        else "Automatic from Server root. Vein launch and monitoring will both use this file."
    )


def update_quick_start_save_games_path(owner) -> None:
    """Show the SaveGames directory derived from the selected server root."""
    automatic = (
        Path(owner.edQuickServerRoot.text().strip() or "Server")
        / "Vein"
        / "Saved"
        / "SaveGames"
    )
    override = owner.edQuickSaveGamesOverride.text().strip()
    use_override = owner.grpQuickSaveGamesOverride.isChecked() and bool(override)
    owner.edQuickSaveGamesResolved.setText(str(Path(override) if use_override else automatic))
    owner.lblQuickSaveGamesMode.setText(
        "Advanced override active. Backups will read worlds from this folder."
        if use_override
        else "Automatic from Server root. Backups will read Vein worlds from this folder."
    )


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
    management_replacement = owner.edQuickManagementWebhook.text().strip()
    management_is_env_reference = management_replacement.upper().startswith("ENV:")

    def reuse_status(label: str) -> str:
        if not management_replacement:
            return f"{label}: enter a literal app webhook above before reusing it."
        if management_is_env_reference:
            return (
                f"{label}: an ENV reference cannot be reused; VEIN Game.ini requires "
                "a literal Discord webhook URL."
            )
        return f"{label}: will reuse the app webhook entered above."

    owner.lblQuickManagementWebhookStatus.setText(
        "App notifications: replacement entered; stored value remains masked in previews."
        if management_replacement
        else getattr(
            owner,
            "_quick_start_management_webhook_summary",
            "App notifications: leave blank to preserve the current management setting.",
        )
    )
    owner.lblQuickDiscordChatWebhookStatus.setText(
        reuse_status("VEIN game chat")
        if owner.chkQuickUseManagementForChat.isChecked()
        else _webhook_status_text(
            "VEIN game chat",
            owner.edQuickDiscordChatWebhook.text(),
            getattr(owner, "_quick_start_existing_chat_webhook_configured", None),
            mode,
        )
    )
    owner.lblQuickDiscordAdminWebhookStatus.setText(
        reuse_status("VEIN admin reports")
        if owner.chkQuickUseManagementForAdmin.isChecked()
        else _webhook_status_text(
            "VEIN admin reports",
            owner.edQuickDiscordAdminWebhook.text(),
            getattr(owner, "_quick_start_existing_admin_webhook_configured", None),
            mode,
        )
    )


def sync_quick_start_webhook_reuse(owner) -> None:
    owner.edQuickDiscordChatWebhook.setEnabled(
        not owner.chkQuickUseManagementForChat.isChecked()
    )
    owner.edQuickDiscordAdminWebhook.setEnabled(
        not owner.chkQuickUseManagementForAdmin.isChecked()
    )
    update_quick_start_webhook_statuses(owner)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def collect_quick_start_values(owner) -> dict[str, Any]:
    return {
        "setup_mode": owner.cmbQuickSetupMode.currentData(),
        "setup_workflow": getattr(owner, "_quick_start_setup_workflow", "new_server"),
        "setup_source": getattr(owner, "_quick_start_setup_source", "quick_start_new"),
        "server_config_fields": sorted(getattr(owner, "_quick_start_dirty_fields", set())),
        "existing_loaded_root": getattr(owner, "_quick_start_existing_loaded_root", ""),
        "server_name": owner.edQuickServerName.text(),
        "server_description": owner.txtQuickServerDescription.toPlainText(),
        "server_root": owner.edQuickServerRoot.text(),
        "steamcmd_path": owner.edQuickSteamCmd.text(),
        "save_games_override": (
            owner.edQuickSaveGamesOverride.text().strip()
            if owner.grpQuickSaveGamesOverride.isChecked()
            else ""
        ),
        "game_log_override": (
            owner.edQuickGameLogOverride.text().strip()
            if owner.grpQuickGameLogOverride.isChecked()
            else ""
        ),
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
        "management_discord_webhook": owner.edQuickManagementWebhook.text(),
        "discord_chat_webhook_url": (
            owner.edQuickManagementWebhook.text()
            if owner.chkQuickUseManagementForChat.isChecked()
            else owner.edQuickDiscordChatWebhook.text()
        ),
        "discord_chat_admin_webhook_url": (
            owner.edQuickManagementWebhook.text()
            if owner.chkQuickUseManagementForAdmin.isChecked()
            else owner.edQuickDiscordAdminWebhook.text()
        ),
    }


def _masked_management_updates(
    value: Any, key: str = "", secret_context: bool = False
) -> Any:
    secret_context = secret_context or "webhook" in key.lower()
    if isinstance(value, dict):
        return {
            item_key: _masked_management_updates(
                item,
                item_key,
                secret_context,
            )
            for item_key, item in value.items()
        }
    if secret_context and isinstance(value, str) and value:
        return value if value.upper().startswith("ENV:") else "<configured, masked>"
    return value


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
    lines.append(
        json.dumps(
            _masked_management_updates(plan.config_updates),
            indent=2,
            sort_keys=True,
        )
    )
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
    content = QtWidgets.QWidget()
    content.setMinimumWidth(620)
    layout = QtWidgets.QVBoxLayout(content)
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
    owner._quick_start_setup_workflow = SetupWorkflow.NEW_SERVER.value
    owner._quick_start_setup_source = "quick_start_new"
    owner._quick_start_compact_existing = False
    owner.lblQuickStartStatus = InlineNotice(
        "Choose whether to configure a new or existing server."
    )
    layout.addWidget(owner.lblQuickStartStatus)
    owner.lblQuickStartStep = QtWidgets.QLabel()
    owner.lblQuickStartStep.setWordWrap(True)
    owner.lblQuickStartStep.setProperty("quickStartStep", True)
    layout.addWidget(owner.lblQuickStartStep)

    owner.quickStartStack = QtWidgets.QStackedWidget()
    location_page = QtWidgets.QGroupBox("Server Location")
    location_grid = QtWidgets.QGridLayout(location_page)
    identity_page = QtWidgets.QGroupBox("Identity & Access")
    identity_grid = QtWidgets.QGridLayout(identity_page)
    network_page = QtWidgets.QGroupBox("Network & Integrations")
    network_grid = QtWidgets.QGridLayout(network_page)
    review_page = QtWidgets.QWidget()
    review_layout = QtWidgets.QVBoxLayout(review_page)
    for page_grid in (location_grid, identity_grid, network_grid):
        page_grid.setVerticalSpacing(8)
        page_grid.setColumnStretch(1, 1)
    for page in (location_page, identity_page, network_page, review_page):
        owner.quickStartStack.addWidget(page)
    layout.addWidget(owner.quickStartStack, 1)

    owner.lblQuickNetworkGuidance = InlineNotice(
        "Public servers normally require the selected UDP gameplay and Steam query "
        "ports through Windows Firewall and your router. Keep the HTTP API private "
        "unless you intentionally secure it. Quick Start does not change firewall "
        "or router settings."
    )

    owner.cmbQuickSetupMode = QtWidgets.QComboBox()
    owner.cmbQuickSetupMode.addItem("Set Up a New Server", NEW_SERVER_MODE)
    owner.cmbQuickSetupMode.addItem("Connect an Existing Server", EXISTING_SERVER_MODE)

    owner.edQuickServerName = _line_edit()
    owner.txtQuickServerDescription = _plain_text("Server rules, gameplay style, or MOTD.")
    owner.edQuickServerRoot = _line_edit("Server")
    owner.edQuickSteamCmd = _line_edit("SteamCMD/steamcmd.exe")
    owner.btnQuickStartBrowseRoot = QtWidgets.QPushButton("Browse…")
    owner.btnQuickStartBrowseRoot.setToolTip("Select the Vein dedicated server folder")
    owner.btnQuickStartBrowseSteamCmd = QtWidgets.QPushButton("Browse…")
    owner.btnQuickStartBrowseSteamCmd.setToolTip("Select steamcmd.exe")
    owner.edQuickSaveGamesResolved = _line_edit()
    owner.edQuickSaveGamesResolved.setReadOnly(True)
    owner.edQuickSaveGamesResolved.setToolTip(
        "Vein stores worlds here. The management app reads this folder for backups."
    )
    owner.lblQuickSaveGamesMode = QtWidgets.QLabel()
    owner.lblQuickSaveGamesMode.setWordWrap(True)
    owner.grpQuickSaveGamesOverride = QtWidgets.QGroupBox("Advanced: override Vein SaveGames folder")
    owner.grpQuickSaveGamesOverride.setCheckable(True)
    owner.grpQuickSaveGamesOverride.setChecked(False)
    save_override_layout = QtWidgets.QHBoxLayout(owner.grpQuickSaveGamesOverride)
    owner.edQuickSaveGamesOverride = _line_edit()
    owner.edQuickSaveGamesOverride.setPlaceholderText(
        "Select a custom SaveGames folder only when required"
    )
    owner.btnQuickSaveGamesBrowse = QtWidgets.QPushButton("Browse…")
    owner.btnQuickSaveGamesBrowse.setToolTip("Select the custom Vein SaveGames folder")
    save_override_layout.addWidget(owner.edQuickSaveGamesOverride, 1)
    save_override_layout.addWidget(owner.btnQuickSaveGamesBrowse)
    owner.edQuickGameLogResolved = _line_edit()
    owner.edQuickGameLogResolved.setReadOnly(True)
    owner.edQuickGameLogResolved.setToolTip(
        "Vein creates this log. The management app uses the same file for live monitoring."
    )
    owner.lblQuickGameLogMode = QtWidgets.QLabel()
    owner.lblQuickGameLogMode.setWordWrap(True)
    owner.grpQuickGameLogOverride = QtWidgets.QGroupBox("Advanced: override Vein game log")
    owner.grpQuickGameLogOverride.setCheckable(True)
    owner.grpQuickGameLogOverride.setChecked(False)
    override_layout = QtWidgets.QHBoxLayout(owner.grpQuickGameLogOverride)
    owner.edQuickGameLogOverride = _line_edit()
    owner.edQuickGameLogOverride.setPlaceholderText("Select a custom Vein.log only when required")
    owner.btnQuickGameLogBrowse = QtWidgets.QPushButton("Browse…")
    owner.btnQuickGameLogBrowse.setToolTip("Select the custom Vein game log file")
    override_layout.addWidget(owner.edQuickGameLogOverride, 1)
    override_layout.addWidget(owner.btnQuickGameLogBrowse)
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
    owner.edQuickManagementWebhook = _line_edit()
    owner.edQuickDiscordChatWebhook = _line_edit()
    owner.edQuickDiscordAdminWebhook = _line_edit()
    for field in (
        owner.edQuickManagementWebhook,
        owner.edQuickDiscordChatWebhook,
        owner.edQuickDiscordAdminWebhook,
    ):
        field.setEchoMode(QtWidgets.QLineEdit.Password)
        field.setPlaceholderText("Leave blank to preserve an existing webhook")
    owner.edQuickManagementWebhook.setPlaceholderText(
        "ENV:DISCORD_WEBHOOK_URL or a Discord webhook URL"
    )
    owner.btnQuickManagementWebhookVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickManagementWebhookVisibility.setCheckable(True)
    owner.btnQuickDiscordChatWebhookVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickDiscordChatWebhookVisibility.setCheckable(True)
    owner.btnQuickDiscordAdminWebhookVisibility = QtWidgets.QPushButton("Show")
    owner.btnQuickDiscordAdminWebhookVisibility.setCheckable(True)
    owner.lblQuickManagementWebhookStatus = QtWidgets.QLabel()
    owner.lblQuickDiscordChatWebhookStatus = QtWidgets.QLabel()
    owner.lblQuickDiscordAdminWebhookStatus = QtWidgets.QLabel()
    owner.lblQuickManagementWebhookStatus.setWordWrap(True)
    owner.lblQuickDiscordChatWebhookStatus.setWordWrap(True)
    owner.lblQuickDiscordAdminWebhookStatus.setWordWrap(True)
    owner.chkQuickUseManagementForChat = QtWidgets.QCheckBox(
        "Use the app notifications webhook for VEIN game chat"
    )
    owner.chkQuickUseManagementForAdmin = QtWidgets.QCheckBox(
        "Use the app notifications webhook for VEIN admin reports"
    )
    owner._quick_start_management_webhook_summary = management_webhook_summary(
        getattr(owner, "config_path", None)
    )

    row = 0
    _add_row(location_grid, row, "Setup mode", owner.cmbQuickSetupMode)
    row += 1
    _add_path_row(
        location_grid,
        row,
        "Server root",
        owner.edQuickServerRoot,
        owner.btnQuickStartBrowseRoot,
    )
    row += 1
    _add_path_row(
        location_grid,
        row,
        "SteamCMD",
        owner.edQuickSteamCmd,
        owner.btnQuickStartBrowseSteamCmd,
    )
    row += 1
    _add_row(location_grid, row, "Vein SaveGames folder", owner.edQuickSaveGamesResolved)
    row += 1
    location_grid.addWidget(owner.lblQuickSaveGamesMode, row, 1)
    row += 1
    location_grid.addWidget(owner.grpQuickSaveGamesOverride, row, 0, 1, 2)
    row += 1
    _add_row(location_grid, row, "Monitored Vein game log", owner.edQuickGameLogResolved)
    row += 1
    location_grid.addWidget(owner.lblQuickGameLogMode, row, 1)
    row += 1
    location_grid.addWidget(owner.grpQuickGameLogOverride, row, 0, 1, 2)
    location_grid.setRowStretch(row + 1, 1)

    row = 0
    for label, field in (
        ("Server name", owner.edQuickServerName),
        ("Description", owner.txtQuickServerDescription),
        ("Max players", owner.spinQuickMaxPlayers),
    ):
        _add_row(identity_grid, row, label, field)
        row += 1
    _add_path_row(
        identity_grid,
        row,
        "Password",
        owner.edQuickPassword,
        owner.btnQuickPasswordVisibility,
    )
    row += 1
    identity_grid.addWidget(owner.lblQuickPasswordStatus, row, 1)
    row += 1
    gameplay_toggles = QtWidgets.QHBoxLayout()
    for checkbox in (
        owner.chkQuickPvp,
        owner.chkQuickVac,
        owner.chkQuickScoreboardBadges,
    ):
        gameplay_toggles.addWidget(checkbox)
    gameplay_toggles.addStretch(1)
    identity_grid.addLayout(gameplay_toggles, row, 0, 1, 2)
    row += 1
    for label, field in (
        ("Admin Steam IDs", owner.txtQuickAdmins),
        ("Super admin Steam IDs", owner.txtQuickSuperAdmins),
        ("Whitelist Steam IDs", owner.txtQuickWhitelist),
    ):
        _add_row(identity_grid, row, label, field)
        row += 1
    identity_grid.setRowStretch(row, 1)

    row = 0
    network_grid.addWidget(owner.lblQuickNetworkGuidance, row, 0, 1, 2)
    row += 1
    for label, field in (
        ("Gameplay port", owner.spinQuickGamePort),
        ("Steam query port", owner.spinQuickQueryPort),
        ("HTTP API port", owner.spinQuickHttpPort),
        ("Bind address", owner.edQuickBindAddr),
    ):
        _add_row(network_grid, row, label, field)
        row += 1
    network_toggles = QtWidgets.QHBoxLayout()
    network_toggles.addWidget(owner.chkQuickPublic)
    network_toggles.addWidget(owner.chkQuickHttpApi)
    network_toggles.addStretch(1)
    network_grid.addLayout(network_toggles, row, 0, 1, 2)
    row += 1
    discord_group = QtWidgets.QGroupBox("Discord Webhooks")
    discord_grid = QtWidgets.QGridLayout(discord_group)
    discord_grid.setVerticalSpacing(6)
    discord_grid.setColumnStretch(1, 1)
    discord_help = QtWidgets.QLabel(
        "App notifications are sent by Vein Server Manager from config.yaml. "
        "VEIN game chat and admin reports are sent by the game from Game.ini. "
        "They may use different Discord channels or the same literal webhook."
    )
    discord_help.setWordWrap(True)
    discord_grid.addWidget(discord_help, 0, 0, 1, 2)
    _add_path_row(
        discord_grid,
        1,
        "App notifications (config.yaml)",
        owner.edQuickManagementWebhook,
        owner.btnQuickManagementWebhookVisibility,
    )
    discord_grid.addWidget(owner.lblQuickManagementWebhookStatus, 2, 1)
    _add_path_row(
        discord_grid,
        3,
        "VEIN game chat (Game.ini)",
        owner.edQuickDiscordChatWebhook,
        owner.btnQuickDiscordChatWebhookVisibility,
    )
    discord_grid.addWidget(owner.chkQuickUseManagementForChat, 4, 1)
    discord_grid.addWidget(owner.lblQuickDiscordChatWebhookStatus, 5, 1)
    _add_path_row(
        discord_grid,
        6,
        "VEIN admin reports (Game.ini)",
        owner.edQuickDiscordAdminWebhook,
        owner.btnQuickDiscordAdminWebhookVisibility,
    )
    discord_grid.addWidget(owner.chkQuickUseManagementForAdmin, 7, 1)
    discord_grid.addWidget(owner.lblQuickDiscordAdminWebhookStatus, 8, 1)
    network_grid.addWidget(discord_group, row, 0, 1, 2)
    network_grid.setRowStretch(row + 1, 1)

    actions = QtWidgets.QHBoxLayout()
    owner.btnQuickStartBack = QtWidgets.QPushButton("Back")
    owner.btnQuickStartNext = QtWidgets.QPushButton("Next")
    owner.btnQuickStartLoadExisting = QtWidgets.QPushButton("Load Existing Settings")
    owner.btnQuickStartLoadExisting.setEnabled(False)
    owner.btnQuickStartConnectExisting = QtWidgets.QPushButton("Connect Existing Server")
    owner.btnQuickStartConnectExisting.setEnabled(False)
    owner.btnQuickStartConnectExisting.setVisible(False)
    owner.btnQuickStartOpenSettings = QtWidgets.QPushButton("Open Server Settings")
    owner.btnQuickStartOpenSettings.setVisible(False)
    owner.btnQuickStartPreview = QtWidgets.QPushButton("Build Preview")
    owner.btnQuickStartApply = QtWidgets.QPushButton("Apply Setup")
    owner.btnQuickStartApply.setEnabled(False)
    set_button_role(owner.btnQuickStartBack, BUTTON_SECONDARY)
    set_button_role(owner.btnQuickStartNext, BUTTON_PRIMARY)
    set_button_role(owner.btnQuickStartLoadExisting, BUTTON_SECONDARY)
    set_button_role(owner.btnQuickStartConnectExisting, BUTTON_PRIMARY)
    set_button_role(owner.btnQuickStartOpenSettings, BUTTON_PRIMARY)
    set_button_role(owner.btnQuickStartPreview, BUTTON_SECONDARY)
    set_button_role(owner.btnQuickStartApply, BUTTON_PRIMARY)
    actions.addWidget(owner.btnQuickStartBack)
    actions.addWidget(owner.btnQuickStartLoadExisting)
    actions.addWidget(owner.btnQuickStartConnectExisting)
    actions.addWidget(owner.btnQuickStartOpenSettings)
    actions.addStretch(1)
    actions.addWidget(owner.btnQuickStartNext)
    actions.addWidget(owner.btnQuickStartPreview)
    actions.addWidget(owner.btnQuickStartApply)
    layout.addLayout(actions)

    owner.txtQuickStartPreview = QtWidgets.QPlainTextEdit()
    owner.txtQuickStartPreview.setReadOnly(True)
    owner.txtQuickStartPreview.setPlaceholderText("Generated setup preview appears here.")
    owner.txtQuickStartPreview.setMinimumHeight(140)
    review_layout.addWidget(
        InlineNotice(
            "Build Preview validates the complete setup and masks passwords and webhook URLs. "
            "Apply Setup remains unavailable until that preview can be applied safely."
        )
    )
    review_layout.addWidget(owner.txtQuickStartPreview, 1)
    owner.btnQuickStartBack.clicked.connect(lambda: move_quick_start_step(owner, -1))
    owner.btnQuickStartNext.clicked.connect(lambda: move_quick_start_step(owner, 1))

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
        "management_discord_webhook": owner.edQuickManagementWebhook,
        "discord_chat_webhook_url": owner.edQuickDiscordChatWebhook,
        "discord_chat_admin_webhook_url": owner.edQuickDiscordAdminWebhook,
        "game_log_override": owner.edQuickGameLogOverride,
        "save_games_override": owner.edQuickSaveGamesOverride,
    }
    owner._quick_start_tracked_widgets = tracked_widgets
    for field, tracked in tracked_widgets.items():
        signal = getattr(tracked, "textChanged", None) or getattr(tracked, "valueChanged", None) or tracked.toggled
        signal.connect(lambda *_, field=field: mark_quick_start_field_changed(owner, field))
    owner.edQuickServerRoot.textChanged.connect(lambda: invalidate_existing_quick_start_load(owner))
    owner.edQuickServerRoot.textChanged.connect(lambda: update_quick_start_game_log_path(owner))
    owner.edQuickServerRoot.textChanged.connect(lambda: update_quick_start_save_games_path(owner))
    owner.edQuickSaveGamesOverride.textChanged.connect(
        lambda: update_quick_start_save_games_path(owner)
    )
    owner.grpQuickSaveGamesOverride.toggled.connect(
        lambda: update_quick_start_save_games_path(owner)
    )
    owner.edQuickGameLogOverride.textChanged.connect(
        lambda: update_quick_start_game_log_path(owner)
    )
    owner.grpQuickGameLogOverride.toggled.connect(
        lambda: update_quick_start_game_log_path(owner)
    )
    owner.edQuickPassword.textChanged.connect(lambda: update_quick_start_password_status(owner))
    owner.btnQuickPasswordVisibility.toggled.connect(
        lambda checked: set_quick_start_password_visibility(owner, checked)
    )
    owner.edQuickDiscordChatWebhook.textChanged.connect(
        lambda: update_quick_start_webhook_statuses(owner)
    )
    owner.edQuickManagementWebhook.textChanged.connect(
        lambda: sync_quick_start_webhook_reuse(owner)
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
    owner.btnQuickManagementWebhookVisibility.toggled.connect(
        lambda checked: set_quick_start_webhook_visibility(
            owner.edQuickManagementWebhook,
            owner.btnQuickManagementWebhookVisibility,
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
    owner.chkQuickUseManagementForChat.toggled.connect(
        lambda: (
            mark_quick_start_field_changed(owner, "discord_chat_webhook_url"),
            sync_quick_start_webhook_reuse(owner),
        )
    )
    owner.chkQuickUseManagementForAdmin.toggled.connect(
        lambda: (
            mark_quick_start_field_changed(owner, "discord_chat_admin_webhook_url"),
            sync_quick_start_webhook_reuse(owner),
        )
    )
    update_quick_start_password_status(owner)
    update_quick_start_webhook_statuses(owner)
    sync_quick_start_webhook_reuse(owner)
    update_quick_start_save_games_path(owner)
    update_quick_start_game_log_path(owner)
    set_quick_start_step(owner, 0)

    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setWidget(content)
    scroll.setProperty("quickStartScroll", True)
    return scroll


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
    owner.btnQuickStartConnectExisting.setEnabled(False)
    owner.btnQuickStartApply.setEnabled(False)
    if existing:
        owner._quick_start_setup_workflow = SetupWorkflow.EXISTING_SERVER.value
        owner._quick_start_setup_source = "existing_import"
        _show_existing_server_actions(owner)
    else:
        if owner._quick_start_setup_workflow != SetupWorkflow.FIRST_SETUP.value:
            owner._quick_start_setup_workflow = SetupWorkflow.NEW_SERVER.value
            owner._quick_start_setup_source = "quick_start_new"
        _show_new_server_wizard(owner)
    owner.lblQuickStartStatus.setText(
        "Select the installed server folder, then load its current settings before connecting it."
        if existing
        else "Enter settings for a new server, then build and review the complete preview."
    )
    owner.lblQuickStartStatus.set_kind("info")
    update_quick_start_password_status(owner)
    update_quick_start_webhook_statuses(owner)


def enforce_quick_start_root_mode(
    owner,
    inspection: ServerRootInspection,
    assessment: SetupAssessment | None = None,
    metadata: SetupMetadata | None = None,
) -> bool:
    """Apply state-aware routing, retaining legacy detection when no assessment is given."""
    if assessment is not None:
        route_quick_start_workflow(owner, assessment, metadata)
        return assessment.workflow == SetupWorkflow.EXISTING_SERVER
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
    owner.btnQuickStartConnectExisting.setEnabled(True)


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
