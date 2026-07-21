"""Curated and advanced guarded server settings views."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from PySide6 import QtCore, QtWidgets

from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    InlineNotice,
    PAGE_MARGIN,
    SECTION_SPACING,
    PageHeader,
    set_button_role,
)
from .preflight import load_config_for_preflight
from .widgets import CollapsibleBox
from Tools.server_config_editor import (
    ServerConfigEdit,
    apply_server_config_edits,
    make_edit,
    preview_server_config_edits,
)
from Tools.server_config_preview import GAME_STATE_SECTION, build_server_config_preview
from Tools.server_config_validator import (
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
)


IDENTITY_ACCESS_TARGETS = {
    "server_name": ("Game.ini", GAME_INI_SECTION, "ServerName"),
    "server_description": ("Game.ini", GAME_INI_SECTION, "ServerDescription"),
    "max_players": ("Game.ini", ENGINE_GAME_SESSION_SECTION, "MaxPlayers"),
    "public": ("Game.ini", GAME_INI_SECTION, "bPublic"),
    "password": ("Game.ini", GAME_INI_SECTION, "Password"),
    "admin_steam_ids": ("Game.ini", GAME_INI_SECTION, "AdminSteamIDs"),
    "super_admin_steam_ids": ("Game.ini", GAME_INI_SECTION, "SuperAdminSteamIDs"),
    "whitelisted_players": ("Game.ini", GAME_STATE_SECTION, "WhitelistedPlayers"),
}

IDENTITY_ACCESS_LABELS = {
    "server_name": "Server name",
    "server_description": "Description",
    "max_players": "Maximum players",
    "public": "Public visibility",
    "password": "Password",
    "admin_steam_ids": "Admin Steam IDs",
    "super_admin_steam_ids": "Super admin Steam IDs",
    "whitelisted_players": "Whitelisted players",
}


def _item_lookup(items: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    return {
        (str(item.get("source")), str(item.get("section")), str(item.get("key"))): item
        for item in items
    }


def _list_from_preview(value: str) -> tuple[str, ...]:
    if not value or value == "(not set)":
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


def identity_access_values_from_preview(
    items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Extract non-secret curated values from the existing preview payload."""
    lookup = _item_lookup(items)

    def item(field: str) -> Mapping[str, Any]:
        return lookup.get(IDENTITY_ACCESS_TARGETS[field], {})

    def scalar(field: str, default: str = "") -> str:
        current = item(field)
        if not current.get("present"):
            return default
        value = str(current.get("value") or "")
        return "" if value == "(not set)" else value

    try:
        max_players = int(scalar("max_players", "8"))
    except ValueError:
        max_players = 8
    public_text = scalar("public", "True").strip().lower()
    return {
        "server_name": scalar("server_name"),
        "server_description": scalar("server_description"),
        "max_players": max(1, min(max_players, 200)),
        "public": public_text in {"1", "true", "yes", "on"},
        "password": "",
        "password_configured": bool(item("password").get("present")),
        "admin_steam_ids": _list_from_preview(scalar("admin_steam_ids")),
        "super_admin_steam_ids": _list_from_preview(scalar("super_admin_steam_ids")),
        "whitelisted_players": _list_from_preview(scalar("whitelisted_players")),
    }


def validate_identity_access_values(values: Mapping[str, Any]) -> dict[str, str]:
    """Return field-specific blocking messages for the curated form."""
    errors: dict[str, str] = {}
    if not str(values.get("server_name") or "").strip():
        errors["server_name"] = "Server name is required."
    try:
        max_players = int(values.get("max_players", 0))
    except (TypeError, ValueError):
        max_players = 0
    if not 1 <= max_players <= 200:
        errors["max_players"] = "Maximum players must be between 1 and 200."
    for field in ("admin_steam_ids", "super_admin_steam_ids", "whitelisted_players"):
        invalid = [value for value in values.get(field, ()) if not (str(value).isdigit() and len(str(value)) == 17)]
        if invalid:
            errors[field] = "Use one 17-digit SteamID64 per line."
    return errors


def build_identity_access_edits(
    values: Mapping[str, Any], baseline: Mapping[str, Any]
) -> tuple[ServerConfigEdit, ...]:
    """Build allowlisted edits only for fields changed in the curated form."""
    errors = validate_identity_access_values(values)
    if errors:
        raise ValueError("Resolve the highlighted General & Access fields before reviewing.")
    edits: list[ServerConfigEdit] = []
    for field, target in IDENTITY_ACCESS_TARGETS.items():
        if field == "password":
            replacement = str(values.get(field) or "")
            if replacement:
                edits.append(make_edit(*target, replacement))
            continue
        value = values.get(field)
        original = baseline.get(field)
        if value == original:
            continue
        if field == "public":
            value = "True" if bool(value) else "False"
        elif field in {"admin_steam_ids", "super_admin_steam_ids", "whitelisted_players"}:
            value = list(value or ())
        else:
            value = str(value)
        edits.append(make_edit(*target, value))
    return tuple(edits)


def identity_access_change_summary(
    values: Mapping[str, Any], baseline: Mapping[str, Any]
) -> str:
    """Describe proposed curated changes without exposing protected values."""
    lines = ["Proposed General & Access changes:"]
    changed = False
    for field in IDENTITY_ACCESS_TARGETS:
        if field == "password":
            if values.get("password"):
                lines.append("- Password: replace the configured password (value hidden)")
                changed = True
            continue
        if values.get(field) != baseline.get(field):
            lines.append(f"- {IDENTITY_ACCESS_LABELS[field]}")
            changed = True
    if not changed:
        lines.append("- No changes")
    lines.extend(("", "A server restart is recommended after applying these settings."))
    return "\n".join(lines)


def mask_sensitive_config_diff(text: str) -> str:
    """Mask secret values in unified INI diffs shown by either editor."""
    secret_keys = {"password", "discordchatwebhookurl", "discordchatadminwebhookurl"}
    output: list[str] = []
    for line in text.splitlines(keepends=True):
        prefix = line[:1]
        body = line[1:] if prefix in {"+", "-"} else line
        if prefix in {"+", "-"} and not body.startswith(("++", "--")) and "=" in body:
            key = body.split("=", 1)[0].strip().lstrip("+").lower()
            if key in secret_keys:
                ending = "\n" if line.endswith("\n") else ""
                line = f"{prefix}{body.split('=', 1)[0]}=<configured, masked>{ending}"
        output.append(line)
    return "".join(output)


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
            payload["diffs"] = {
                path: mask_sensitive_config_diff(diff)
                for path, diff in payload.get("diffs", {}).items()
            }
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


class IdentityAccessEditWorker(QtCore.QRunnable):
    """Preview or apply a curated batch through the guarded config writer."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        action: str,
        values: Mapping[str, Any],
        baseline: Mapping[str, Any],
    ):
        super().__init__()
        self.config_path = Path(config_path)
        self.action = action
        self.values = dict(values)
        self.baseline = dict(baseline)
        self.signals = ServerConfigEditSignals()

    def run(self) -> None:
        try:
            cfg = load_config_for_preflight(self.config_path)
            edits = build_identity_access_edits(self.values, self.baseline)
            result = (
                apply_server_config_edits(cfg, edits)
                if self.action == "apply"
                else preview_server_config_edits(cfg, edits)
            )
            payload = result.as_dict()
            payload["diffs"] = {
                path: mask_sensitive_config_diff(diff)
                for path, diff in payload.get("diffs", {}).items()
            }
            payload.update(
                {
                    "ok": True,
                    "action": self.action,
                    "error": "",
                    "summary": identity_access_change_summary(self.values, self.baseline),
                }
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "action": self.action,
                "error": str(exc),
                "diffs": {},
                "changed_files": [],
                "backups": [],
                "validation": [],
                "summary": "",
            }
        self.signals.ready.emit(payload)


def _steam_id_lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def collect_identity_access_values(owner) -> dict[str, Any]:
    return {
        "server_name": owner.edServerIdentityName.text().strip(),
        "server_description": owner.txtServerIdentityDescription.toPlainText().strip(),
        "max_players": owner.spinServerIdentityMaxPlayers.value(),
        "public": owner.chkServerIdentityPublic.isChecked(),
        "password": owner.edServerIdentityPassword.text(),
        "admin_steam_ids": _steam_id_lines(owner.txtServerIdentityAdmins.toPlainText()),
        "super_admin_steam_ids": _steam_id_lines(owner.txtServerIdentitySuperAdmins.toPlainText()),
        "whitelisted_players": _steam_id_lines(owner.txtServerIdentityWhitelist.toPlainText()),
    }


def update_identity_access_form_state(owner) -> None:
    if getattr(owner, "_server_identity_loading", False):
        return
    values = collect_identity_access_values(owner)
    baseline = getattr(owner, "_server_identity_baseline", {})
    errors = validate_identity_access_values(values)
    owner.lblServerIdentityNameError.setText(errors.get("server_name", ""))
    owner.lblServerIdentitySteamIdError.setText(
        next(
            (
                errors[field]
                for field in ("admin_steam_ids", "super_admin_steam_ids", "whitelisted_players")
                if field in errors
            ),
            "",
        )
    )
    dirty = any(
        values.get(field) != baseline.get(field)
        for field in IDENTITY_ACCESS_TARGETS
        if field != "password"
    ) or bool(values.get("password"))
    owner._server_identity_dirty = dirty
    if errors:
        owner.lblServerIdentityState.setText("Resolve the highlighted fields before previewing changes.")
        owner.lblServerIdentityState.set_kind("error")
    elif dirty:
        owner.lblServerIdentityState.setText(
            "Unsaved changes. Preview the complete change set before applying it."
        )
        owner.lblServerIdentityState.set_kind("warning")
    else:
        owner.lblServerIdentityState.setText("General & Access settings are current.")
        owner.lblServerIdentityState.set_kind("success")
    owner.btnServerIdentityPreview.setEnabled(dirty and not errors)
    owner.btnServerIdentityApply.setEnabled(False)
    owner.btnServerIdentityReset.setEnabled(dirty)
    if dirty:
        owner.txtServerIdentityPreview.clear()
        if hasattr(owner, "boxServerSettingsReview"):
            owner.boxServerSettingsReview.toggle.setChecked(False)


def populate_identity_access_form(owner, items: Sequence[Mapping[str, Any]]) -> None:
    values = identity_access_values_from_preview(items)
    owner._server_identity_loading = True
    try:
        owner.edServerIdentityName.setText(values["server_name"])
        owner.txtServerIdentityDescription.setPlainText(values["server_description"])
        owner.spinServerIdentityMaxPlayers.setValue(values["max_players"])
        owner.chkServerIdentityPublic.setChecked(values["public"])
        owner.edServerIdentityPassword.clear()
        owner.txtServerIdentityAdmins.setPlainText("\n".join(values["admin_steam_ids"]))
        owner.txtServerIdentitySuperAdmins.setPlainText(
            "\n".join(values["super_admin_steam_ids"])
        )
        owner.txtServerIdentityWhitelist.setPlainText("\n".join(values["whitelisted_players"]))
        owner.lblServerIdentityPasswordStatus.setText(
            "Password is configured and will be preserved unless a replacement is entered."
            if values["password_configured"]
            else "No password is currently configured. Leave blank to keep the server open."
        )
        owner._server_identity_password_configured = values["password_configured"]
        owner._server_identity_baseline = {
            key: value for key, value in values.items() if key != "password_configured"
        }
    finally:
        owner._server_identity_loading = False
    owner.txtServerIdentityPreview.clear()
    if hasattr(owner, "boxServerSettingsReview"):
        owner.boxServerSettingsReview.toggle.setChecked(False)
    update_identity_access_form_state(owner)


def reset_identity_access_form(owner) -> None:
    baseline = getattr(owner, "_server_identity_baseline", {})
    if not baseline:
        return
    items = []
    for field, (source, section, key) in IDENTITY_ACCESS_TARGETS.items():
        if field == "password":
            items.append(
                {
                    "source": source,
                    "section": section,
                    "key": key,
                    "value": "<configured, masked>",
                    "present": bool(getattr(owner, "_server_identity_password_configured", False)),
                }
            )
            continue
        value = baseline.get(field)
        if isinstance(value, tuple):
            display = ", ".join(value)
        elif field == "public":
            display = "True" if value else "False"
        else:
            display = str(value or "")
        items.append(
            {
                "source": source,
                "section": section,
                "key": key,
                "value": display,
                "present": bool(display),
            }
        )
    populate_identity_access_form(owner, items)


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

    owner.tabsServerSettings = QtWidgets.QTabWidget()
    simple_page = QtWidgets.QScrollArea()
    simple_page.setWidgetResizable(True)
    simple_page.setFrameShape(QtWidgets.QFrame.NoFrame)
    simple_content = QtWidgets.QWidget()
    simple_layout = QtWidgets.QVBoxLayout(simple_content)
    simple_layout.setContentsMargins(0, 8, 0, 0)
    simple_layout.setSpacing(SECTION_SPACING)
    simple_page.setWidget(simple_content)
    advanced_page = QtWidgets.QWidget()
    advanced_layout = QtWidgets.QVBoxLayout(advanced_page)
    advanced_layout.setContentsMargins(0, 8, 0, 0)
    advanced_layout.setSpacing(SECTION_SPACING)
    owner.tabsServerSettings.addTab(simple_page, "General & Access")
    owner.tabsServerSettings.addTab(advanced_page, "Advanced Settings")
    layout.addWidget(owner.tabsServerSettings, 1)

    owner._server_identity_loading = False
    owner._server_identity_baseline = {}
    owner._server_identity_password_configured = False
    owner._server_identity_dirty = False
    owner.lblServerIdentityState = InlineNotice(
        "Refresh to load the current General & Access settings."
    )

    identity_group = QtWidgets.QGroupBox("Server Identity")
    identity_grid = QtWidgets.QGridLayout(identity_group)
    identity_grid.setColumnStretch(1, 1)
    owner.edServerIdentityName = QtWidgets.QLineEdit()
    owner.edServerIdentityName.setPlaceholderText("Required server name")
    owner.lblServerIdentityNameError = QtWidgets.QLabel()
    owner.lblServerIdentityNameError.setWordWrap(True)
    owner.lblServerIdentityNameError.setProperty("fieldError", True)
    owner.txtServerIdentityDescription = QtWidgets.QPlainTextEdit()
    owner.txtServerIdentityDescription.setPlaceholderText(
        "Server rules, play style, or a short welcome message"
    )
    owner.txtServerIdentityDescription.setMaximumHeight(82)
    owner.spinServerIdentityMaxPlayers = QtWidgets.QSpinBox()
    owner.spinServerIdentityMaxPlayers.setRange(1, 200)
    owner.chkServerIdentityPublic = QtWidgets.QCheckBox(
        "List this server publicly"
    )
    identity_grid.addWidget(QtWidgets.QLabel("Server name"), 0, 0)
    identity_grid.addWidget(owner.edServerIdentityName, 0, 1)
    identity_grid.addWidget(owner.lblServerIdentityNameError, 1, 1)
    identity_grid.addWidget(QtWidgets.QLabel("Description"), 2, 0)
    identity_grid.addWidget(owner.txtServerIdentityDescription, 2, 1)
    identity_grid.addWidget(QtWidgets.QLabel("Maximum players"), 3, 0)
    identity_grid.addWidget(owner.spinServerIdentityMaxPlayers, 3, 1)
    identity_grid.addWidget(owner.chkServerIdentityPublic, 4, 1)
    simple_layout.addWidget(identity_group)

    access_group = QtWidgets.QGroupBox("Access")
    access_grid = QtWidgets.QGridLayout(access_group)
    access_grid.setColumnStretch(1, 1)
    owner.edServerIdentityPassword = QtWidgets.QLineEdit()
    owner.edServerIdentityPassword.setEchoMode(QtWidgets.QLineEdit.Password)
    owner.edServerIdentityPassword.setPlaceholderText(
        "Leave blank to preserve the current password"
    )
    owner.btnServerIdentityPasswordVisibility = QtWidgets.QPushButton("Show")
    owner.btnServerIdentityPasswordVisibility.setCheckable(True)
    password_row = QtWidgets.QWidget()
    password_layout = QtWidgets.QHBoxLayout(password_row)
    password_layout.setContentsMargins(0, 0, 0, 0)
    password_layout.addWidget(owner.edServerIdentityPassword, 1)
    password_layout.addWidget(owner.btnServerIdentityPasswordVisibility)
    owner.lblServerIdentityPasswordStatus = QtWidgets.QLabel(
        "Password status will appear after Refresh."
    )
    owner.lblServerIdentityPasswordStatus.setWordWrap(True)
    owner.txtServerIdentityAdmins = QtWidgets.QPlainTextEdit()
    owner.txtServerIdentitySuperAdmins = QtWidgets.QPlainTextEdit()
    owner.txtServerIdentityWhitelist = QtWidgets.QPlainTextEdit()
    for field in (
        owner.txtServerIdentityAdmins,
        owner.txtServerIdentitySuperAdmins,
        owner.txtServerIdentityWhitelist,
    ):
        field.setMaximumHeight(68)
        field.setPlaceholderText("One 17-digit SteamID64 per line")
    owner.lblServerIdentitySteamIdError = QtWidgets.QLabel()
    owner.lblServerIdentitySteamIdError.setWordWrap(True)
    owner.lblServerIdentitySteamIdError.setProperty("fieldError", True)
    access_grid.addWidget(QtWidgets.QLabel("Replacement password"), 0, 0)
    access_grid.addWidget(password_row, 0, 1)
    access_grid.addWidget(owner.lblServerIdentityPasswordStatus, 1, 1)
    access_grid.addWidget(QtWidgets.QLabel("Admin Steam IDs"), 2, 0)
    access_grid.addWidget(owner.txtServerIdentityAdmins, 2, 1)
    access_grid.addWidget(QtWidgets.QLabel("Super admin Steam IDs"), 3, 0)
    access_grid.addWidget(owner.txtServerIdentitySuperAdmins, 3, 1)
    access_grid.addWidget(QtWidgets.QLabel("Whitelisted players"), 4, 0)
    access_grid.addWidget(owner.txtServerIdentityWhitelist, 4, 1)
    access_grid.addWidget(owner.lblServerIdentitySteamIdError, 5, 1)
    simple_layout.addWidget(access_group)

    owner.txtServerIdentityPreview = QtWidgets.QPlainTextEdit()
    owner.txtServerIdentityPreview.setReadOnly(True)
    owner.txtServerIdentityPreview.setMinimumHeight(120)
    owner.txtServerIdentityPreview.setPlaceholderText(
        "A human-readable summary and masked INI diff will appear here."
    )
    owner.btnServerIdentityReset = QtWidgets.QPushButton("Discard Changes")
    owner.btnServerIdentityPreview = QtWidgets.QPushButton("Review Changes")
    owner.btnServerIdentityApply = QtWidgets.QPushButton("Apply Changes")
    for button in (
        owner.btnServerIdentityReset,
        owner.btnServerIdentityPreview,
        owner.btnServerIdentityApply,
    ):
        button.setEnabled(False)
    set_button_role(owner.btnServerIdentityReset, BUTTON_SECONDARY)
    set_button_role(owner.btnServerIdentityPreview, BUTTON_SECONDARY)
    set_button_role(owner.btnServerIdentityApply, BUTTON_PRIMARY)

    owner.btnServerIdentityReset.clicked.connect(
        lambda: reset_identity_access_form(owner)
    )
    owner.btnServerIdentityPasswordVisibility.toggled.connect(
        lambda visible: (
            owner.edServerIdentityPassword.setEchoMode(
                QtWidgets.QLineEdit.Normal if visible else QtWidgets.QLineEdit.Password
            ),
            owner.btnServerIdentityPasswordVisibility.setText(
                "Hide" if visible else "Show"
            ),
        )
    )
    for field in (
        owner.edServerIdentityName,
        owner.txtServerIdentityDescription,
        owner.spinServerIdentityMaxPlayers,
        owner.chkServerIdentityPublic,
        owner.edServerIdentityPassword,
        owner.txtServerIdentityAdmins,
        owner.txtServerIdentitySuperAdmins,
        owner.txtServerIdentityWhitelist,
    ):
        signal = (
            getattr(field, "textChanged", None)
            or getattr(field, "valueChanged", None)
            or field.toggled
        )
        signal.connect(lambda *_: update_identity_access_form_state(owner))

    owner.treeServerConfigPreview = QtWidgets.QTreeWidget()
    owner.treeServerConfigPreview.setColumnCount(5)
    owner.treeServerConfigPreview.setHeaderLabels(["File", "Section", "Key", "Value", "State"])
    owner.treeServerConfigPreview.setRootIsDecorated(False)
    owner.treeServerConfigPreview.setAlternatingRowColors(True)
    owner.treeServerConfigPreview.setSortingEnabled(True)
    owner.treeServerConfigPreview.setTextElideMode(QtCore.Qt.ElideMiddle)
    owner.treeServerConfigPreview.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    advanced_layout.addWidget(
        InlineNotice(
            "Advanced Settings exposes the allowlisted INI table. Use General & Access "
            "for routine changes and this view for individual technical settings."
        )
    )
    advanced_layout.addWidget(owner.treeServerConfigPreview, 1)

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
    advanced_layout.addWidget(edit_group)

    owner.boxServerSettingsReview = CollapsibleBox("Change Review")
    owner.boxServerSettingsReview.layout_for_rows().addWidget(
        owner.txtServerIdentityPreview
    )
    owner.boxServerSettingsReview.toggle.setChecked(False)
    layout.addWidget(owner.boxServerSettingsReview)

    owner.frmServerSettingsActions = QtWidgets.QFrame()
    owner.frmServerSettingsActions.setProperty("settingsActionBar", True)
    shared_actions_layout = QtWidgets.QVBoxLayout(owner.frmServerSettingsActions)
    shared_actions_layout.setContentsMargins(8, 8, 8, 8)
    shared_actions_layout.setSpacing(8)
    shared_actions_layout.addWidget(owner.lblServerIdentityState)
    identity_actions = QtWidgets.QHBoxLayout()
    identity_actions.addWidget(owner.btnServerIdentityReset)
    identity_actions.addStretch(1)
    identity_actions.addWidget(owner.btnServerIdentityPreview)
    identity_actions.addWidget(owner.btnServerIdentityApply)
    shared_actions_layout.addLayout(identity_actions)
    layout.addWidget(owner.frmServerSettingsActions)

    def update_shared_action_visibility(index: int) -> None:
        curated = index == 0
        owner.frmServerSettingsActions.setVisible(curated)
        owner.boxServerSettingsReview.setVisible(curated)

    owner.tabsServerSettings.currentChanged.connect(
        update_shared_action_visibility
    )
    update_shared_action_visibility(owner.tabsServerSettings.currentIndex())

    return widget
