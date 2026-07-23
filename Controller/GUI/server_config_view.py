"""Curated and advanced guarded server settings views."""

from __future__ import annotations

import ipaddress
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
from Tools.server_config_preview import (
    CONSOLE_VARIABLES_SECTION,
    GAME_STATE_SECTION,
    SERVER_SETTINGS_SECTION,
    build_server_config_preview,
)
from Tools.server_config_validator import (
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
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
    "pvp_enabled": ("Engine.ini", CONSOLE_VARIABLES_SECTION, "vein.PvP"),
    "vac_enabled": ("Game.ini", ONLINE_STEAM_SECTION, "bVACEnabled"),
    "ai_spawner_enabled": (
        "Engine.ini",
        CONSOLE_VARIABLES_SECTION,
        "vein.AISpawner.Enabled",
    ),
    "time_multiplier": (
        "Engine.ini",
        CONSOLE_VARIABLES_SECTION,
        "vein.TimeMultiplier",
    ),
    "show_scoreboard_badges": (
        "Game.ini",
        SERVER_SETTINGS_SECTION,
        "GS_ShowScoreboardBadges",
    ),
    "bind_addr": ("Game.ini", GAME_INI_SECTION, "BindAddr"),
    "game_port": ("Game.ini", URL_SECTION, "Port"),
    "query_port": ("Game.ini", ONLINE_STEAM_SECTION, "GameServerQueryPort"),
    "http_port": ("Game.ini", GAME_INI_SECTION, "HTTPPort"),
    "heartbeat_interval": ("Game.ini", GAME_INI_SECTION, "HeartbeatInterval"),
    "discord_chat_webhook_url": (
        "Game.ini",
        SERVER_SETTINGS_SECTION,
        "DiscordChatWebhookURL",
    ),
    "discord_chat_admin_webhook_url": (
        "Game.ini",
        SERVER_SETTINGS_SECTION,
        "DiscordChatAdminWebhookURL",
    ),
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
    "pvp_enabled": "PvP",
    "vac_enabled": "VAC protection",
    "ai_spawner_enabled": "AI spawning",
    "time_multiplier": "Time multiplier",
    "show_scoreboard_badges": "Admin scoreboard badges",
    "bind_addr": "Bind address",
    "game_port": "Gameplay port",
    "query_port": "Steam query port",
    "http_port": "HTTP API port",
    "heartbeat_interval": "Heartbeat interval",
    "discord_chat_webhook_url": "VEIN game chat webhook",
    "discord_chat_admin_webhook_url": "VEIN admin reports webhook",
}

PROTECTED_REPLACEMENT_FIELDS = {
    "password",
    "discord_chat_webhook_url",
    "discord_chat_admin_webhook_url",
}

LIST_FIELDS = {
    "admin_steam_ids",
    "super_admin_steam_ids",
    "whitelisted_players",
}

BOOLEAN_FIELDS = {
    "public",
    "pvp_enabled",
    "vac_enabled",
    "ai_spawner_enabled",
    "show_scoreboard_badges",
}

CURATED_TAB_FIELDS = (
    ("General", ("server_name", "server_description", "max_players", "public")),
    (
        "Access",
        ("password", "admin_steam_ids", "super_admin_steam_ids", "whitelisted_players"),
    ),
    (
        "Gameplay",
        (
            "pvp_enabled",
            "vac_enabled",
            "ai_spawner_enabled",
            "time_multiplier",
            "show_scoreboard_badges",
        ),
    ),
    (
        "Network",
        ("bind_addr", "game_port", "query_port", "http_port", "heartbeat_interval"),
    ),
    (
        "Discord",
        ("discord_chat_webhook_url", "discord_chat_admin_webhook_url"),
    ),
)


def _field_help(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setProperty("fieldHelp", True)
    return label


def _field_changed(field: str, values: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    if field in PROTECTED_REPLACEMENT_FIELDS:
        return bool(values.get(field))
    return values.get(field) != baseline.get(field)


def update_curated_tab_markers(
    owner, values: Mapping[str, Any], baseline: Mapping[str, Any]
) -> None:
    """Mark curated tabs containing unsaved values without changing navigation."""
    tabs = getattr(owner, "tabsServerSettings", None)
    if tabs is None:
        return
    for index, (label, fields) in enumerate(CURATED_TAB_FIELDS):
        changed = any(_field_changed(field, values, baseline) for field in fields)
        tabs.setTabText(index, f"{label} *" if changed else label)


def summarize_server_config_validation(
    checks: Sequence[Mapping[str, Any]],
) -> str:
    """Return a compact operator-facing summary of post-write validation."""
    counts = {"PASS": 0, "INFO": 0, "WARN": 0, "FAIL": 0}
    for check in checks:
        status = str(check.get("status") or "").upper()
        if status in counts:
            counts[status] += 1
    parts = [f"{status}={count}" for status, count in counts.items() if count]
    return "Validation: " + (", ".join(parts) if parts else "no checks reported")


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

    def boolean(field: str, default: bool) -> bool:
        text = scalar(field, "True" if default else "False").strip().lower()
        return text in {"1", "true", "yes", "on"}

    def integer(field: str, default: int) -> int:
        try:
            return int(scalar(field, str(default)))
        except ValueError:
            return default

    def decimal(field: str, default: float) -> float:
        try:
            return float(scalar(field, str(default)))
        except ValueError:
            return default

    try:
        max_players = int(scalar("max_players", "8"))
    except ValueError:
        max_players = 8
    return {
        "server_name": scalar("server_name"),
        "server_description": scalar("server_description"),
        "max_players": max(1, min(max_players, 200)),
        "public": boolean("public", True),
        "password": "",
        "password_configured": bool(item("password").get("present")),
        "admin_steam_ids": _list_from_preview(scalar("admin_steam_ids")),
        "super_admin_steam_ids": _list_from_preview(scalar("super_admin_steam_ids")),
        "whitelisted_players": _list_from_preview(scalar("whitelisted_players")),
        "pvp_enabled": boolean("pvp_enabled", True),
        "vac_enabled": boolean("vac_enabled", False),
        "ai_spawner_enabled": boolean("ai_spawner_enabled", True),
        "time_multiplier": max(0.1, min(decimal("time_multiplier", 1.0), 100.0)),
        "show_scoreboard_badges": boolean("show_scoreboard_badges", True),
        "bind_addr": scalar("bind_addr", "0.0.0.0"),
        "game_port": max(1, min(integer("game_port", 7777), 65535)),
        "query_port": max(1, min(integer("query_port", 27015), 65535)),
        "http_port": max(1, min(integer("http_port", 8080), 65535)),
        "heartbeat_interval": max(1, min(integer("heartbeat_interval", 5), 3600)),
        "discord_chat_webhook_url": "",
        "discord_chat_webhook_configured": bool(
            item("discord_chat_webhook_url").get("present")
        ),
        "discord_chat_admin_webhook_url": "",
        "discord_chat_admin_webhook_configured": bool(
            item("discord_chat_admin_webhook_url").get("present")
        ),
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
    bind_addr = str(values.get("bind_addr", "0.0.0.0") or "").strip()
    try:
        ipaddress.ip_address(bind_addr)
    except ValueError:
        errors["bind_addr"] = "Use a valid IPv4 or IPv6 bind address."
    ports = {
        "game_port": int(values.get("game_port", 7777)),
        "query_port": int(values.get("query_port", 27015)),
        "http_port": int(values.get("http_port", 8080)),
    }
    if len(set(ports.values())) != len(ports):
        errors["ports"] = "Gameplay, query, and HTTP API ports must be different."
    for field in ("discord_chat_webhook_url", "discord_chat_admin_webhook_url"):
        url = str(values.get(field) or "").strip().strip('"')
        if url and not url.lower().startswith(
            ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")
        ):
            errors[field] = "Enter a Discord webhook URL or leave blank to preserve it."
    return errors


def build_identity_access_edits(
    values: Mapping[str, Any], baseline: Mapping[str, Any]
) -> tuple[ServerConfigEdit, ...]:
    """Build allowlisted edits only for fields changed in the curated form."""
    errors = validate_identity_access_values(values)
    if errors:
        raise ValueError("Resolve the highlighted Server Settings fields before reviewing.")
    edits: list[ServerConfigEdit] = []
    for field, target in IDENTITY_ACCESS_TARGETS.items():
        if field in PROTECTED_REPLACEMENT_FIELDS:
            replacement = str(values.get(field) or "")
            if replacement:
                if field.startswith("discord_"):
                    replacement = replacement.strip().strip('"')
                    replacement = f'"{replacement}"'
                edits.append(make_edit(*target, replacement))
            continue
        value = values.get(field)
        original = baseline.get(field)
        if value == original:
            continue
        if field in {"public", "pvp_enabled", "ai_spawner_enabled"}:
            value = "True" if bool(value) else "False"
        elif field in {"vac_enabled", "show_scoreboard_badges"}:
            value = "1" if bool(value) else "0"
        elif field in LIST_FIELDS:
            value = list(value or ())
        else:
            value = str(value)
        edits.append(make_edit(*target, value))
    return tuple(edits)


def identity_access_change_summary(
    values: Mapping[str, Any], baseline: Mapping[str, Any]
) -> str:
    """Describe changed curated values without exposing protected values."""
    def display(value: Any) -> str:
        if isinstance(value, bool):
            return "On" if value else "Off"
        if isinstance(value, (tuple, list)):
            return ", ".join(str(item) for item in value) or "None"
        text = str(value or "(blank)").replace("\n", " ")
        return text if len(text) <= 100 else text[:97] + "..."

    lines = ["Changed Server Settings:"]
    changed = False
    for field in IDENTITY_ACCESS_TARGETS:
        if field in PROTECTED_REPLACEMENT_FIELDS:
            if values.get(field):
                lines.append(
                    f"- {IDENTITY_ACCESS_LABELS[field]}: replacement entered (hidden)"
                )
                changed = True
            continue
        if values.get(field) != baseline.get(field):
            lines.append(
                f"- {IDENTITY_ACCESS_LABELS[field]}: "
                f"{display(baseline.get(field))} -> {display(values.get(field))}"
            )
            changed = True
    if not changed:
        lines.append("- No changes")
    lines.extend(("", "A server restart is recommended after applying these settings."))
    return "\n".join(lines)


def confirm_identity_access_changes(
    parent, summary: str, diffs: Mapping[str, Any]
) -> bool:
    """Confirm a generated Server Settings preview as part of Apply."""
    dialog = QtWidgets.QMessageBox(parent)
    dialog.setIcon(QtWidgets.QMessageBox.Question)
    dialog.setWindowTitle("Review Server Settings Changes")
    dialog.setText("Apply these Server Settings changes?")
    dialog.setInformativeText(summary)
    technical = "\n".join(str(value) for value in diffs.values()).strip()
    if technical:
        dialog.setDetailedText(
            "Technical INI diff (protected values are masked):\n\n" + technical
        )
    apply_button = dialog.addButton(
        "Apply Changes", QtWidgets.QMessageBox.AcceptRole
    )
    dialog.addButton(QtWidgets.QMessageBox.Cancel)
    dialog.setDefaultButton(apply_button)
    dialog.exec()
    return dialog.clickedButton() is apply_button


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
        "pvp_enabled": owner.chkServerGameplayPvp.isChecked(),
        "vac_enabled": owner.chkServerGameplayVac.isChecked(),
        "ai_spawner_enabled": owner.chkServerGameplayAiSpawner.isChecked(),
        "time_multiplier": owner.spinServerGameplayTimeMultiplier.value(),
        "show_scoreboard_badges": owner.chkServerGameplayScoreboardBadges.isChecked(),
        "bind_addr": owner.edServerNetworkBindAddress.text().strip(),
        "game_port": owner.spinServerNetworkGamePort.value(),
        "query_port": owner.spinServerNetworkQueryPort.value(),
        "http_port": owner.spinServerNetworkHttpPort.value(),
        "heartbeat_interval": owner.spinServerNetworkHeartbeat.value(),
        "discord_chat_webhook_url": owner.edServerDiscordChatWebhook.text(),
        "discord_chat_admin_webhook_url": owner.edServerDiscordAdminWebhook.text(),
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
    owner.lblServerNetworkBindError.setText(errors.get("bind_addr", ""))
    owner.lblServerNetworkPortsError.setText(errors.get("ports", ""))
    owner.lblServerDiscordChatError.setText(
        errors.get("discord_chat_webhook_url", "")
    )
    owner.lblServerDiscordAdminError.setText(
        errors.get("discord_chat_admin_webhook_url", "")
    )
    dirty = any(
        _field_changed(field, values, baseline) for field in IDENTITY_ACCESS_TARGETS
    )
    update_curated_tab_markers(owner, values, baseline)
    owner._server_identity_dirty = dirty
    if errors:
        owner.lblServerIdentityState.setText("Resolve the highlighted fields before applying changes.")
        owner.lblServerIdentityState.set_kind("error")
    elif dirty:
        owner._server_settings_apply_notice = ""
        owner._server_settings_apply_notice_kind = "success"
        owner.lblServerIdentityState.setText(
            "Unsaved changes. Apply Changes will show a final review before saving."
        )
        owner.lblServerIdentityState.set_kind("warning")
    elif getattr(owner, "_server_settings_apply_notice", ""):
        owner.lblServerIdentityState.setText(owner._server_settings_apply_notice)
        owner.lblServerIdentityState.set_kind(
            getattr(owner, "_server_settings_apply_notice_kind", "success")
        )
    else:
        owner.lblServerIdentityState.setText("Server Settings are current.")
        owner.lblServerIdentityState.set_kind("success")
    owner.btnServerIdentityApply.setEnabled(dirty and not errors)
    owner.btnServerIdentityReset.setEnabled(dirty)


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
        owner.chkServerGameplayPvp.setChecked(values["pvp_enabled"])
        owner.chkServerGameplayVac.setChecked(values["vac_enabled"])
        owner.chkServerGameplayAiSpawner.setChecked(values["ai_spawner_enabled"])
        owner.spinServerGameplayTimeMultiplier.setValue(values["time_multiplier"])
        owner.chkServerGameplayScoreboardBadges.setChecked(
            values["show_scoreboard_badges"]
        )
        owner.edServerNetworkBindAddress.setText(values["bind_addr"])
        owner.spinServerNetworkGamePort.setValue(values["game_port"])
        owner.spinServerNetworkQueryPort.setValue(values["query_port"])
        owner.spinServerNetworkHttpPort.setValue(values["http_port"])
        owner.spinServerNetworkHeartbeat.setValue(values["heartbeat_interval"])
        owner.edServerDiscordChatWebhook.clear()
        owner.edServerDiscordAdminWebhook.clear()
        owner.lblServerIdentityPasswordStatus.setText(
            "Password is configured and will be preserved unless a replacement is entered."
            if values["password_configured"]
            else "No password is currently configured. Leave blank to keep the server open."
        )
        owner._server_identity_password_configured = values["password_configured"]
        owner._server_discord_chat_webhook_configured = values[
            "discord_chat_webhook_configured"
        ]
        owner._server_discord_admin_webhook_configured = values[
            "discord_chat_admin_webhook_configured"
        ]
        owner.lblServerDiscordChatStatus.setText(
            "Game chat webhook is configured and will be preserved unless replaced."
            if values["discord_chat_webhook_configured"]
            else "No game chat webhook is configured."
        )
        owner.lblServerDiscordAdminStatus.setText(
            "Admin reports webhook is configured and will be preserved unless replaced."
            if values["discord_chat_admin_webhook_configured"]
            else "No admin reports webhook is configured."
        )
        owner._server_identity_baseline = {
            key: value
            for key, value in values.items()
            if not key.endswith("_configured")
        }
    finally:
        owner._server_identity_loading = False
    update_identity_access_form_state(owner)


def reset_identity_access_form(owner) -> None:
    baseline = getattr(owner, "_server_identity_baseline", {})
    if not baseline:
        return
    items = []
    for field, (source, section, key) in IDENTITY_ACCESS_TARGETS.items():
        if field in PROTECTED_REPLACEMENT_FIELDS:
            configured_attr = {
                "password": "_server_identity_password_configured",
                "discord_chat_webhook_url": "_server_discord_chat_webhook_configured",
                "discord_chat_admin_webhook_url": "_server_discord_admin_webhook_configured",
            }[field]
            items.append(
                {
                    "source": source,
                    "section": section,
                    "key": key,
                    "value": "<configured, masked>",
                    "present": bool(getattr(owner, configured_attr, False)),
                }
            )
            continue
        value = baseline.get(field)
        if isinstance(value, tuple):
            display = ", ".join(value)
        elif field in BOOLEAN_FIELDS:
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
    header = QtWidgets.QHBoxLayout()
    owner.lblServerConfigPreviewStatus = QtWidgets.QLabel("Refresh to inspect Game.ini and Engine.ini.")
    owner.lblServerConfigPreviewStatus.setWordWrap(True)
    owner.lblServerConfigPreviewStatus.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    owner.btnServerConfigPreviewRefresh = QtWidgets.QPushButton("Refresh")
    header.addWidget(owner.lblServerConfigPreviewStatus, 1)
    header.addWidget(owner.btnServerConfigPreviewRefresh)
    layout.addLayout(header)

    owner.tabsServerSettings = QtWidgets.QTabWidget()

    def scroll_page() -> tuple[QtWidgets.QScrollArea, QtWidgets.QVBoxLayout]:
        page = QtWidgets.QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        page_layout = QtWidgets.QVBoxLayout(content)
        page_layout.setContentsMargins(0, 8, 0, 0)
        page_layout.setSpacing(SECTION_SPACING)
        page.setWidget(content)
        return page, page_layout

    general_page, general_layout = scroll_page()
    access_page, access_layout = scroll_page()
    gameplay_page, gameplay_layout = scroll_page()
    network_page, network_layout = scroll_page()
    discord_page, discord_layout = scroll_page()
    advanced_page = QtWidgets.QWidget()
    advanced_layout = QtWidgets.QVBoxLayout(advanced_page)
    advanced_layout.setContentsMargins(0, 8, 0, 0)
    advanced_layout.setSpacing(SECTION_SPACING)
    owner.tabsServerSettings.addTab(general_page, "General")
    owner.tabsServerSettings.addTab(access_page, "Access")
    owner.tabsServerSettings.addTab(gameplay_page, "Gameplay")
    owner.tabsServerSettings.addTab(network_page, "Network")
    owner.tabsServerSettings.addTab(discord_page, "Discord")
    owner.tabsServerSettings.addTab(advanced_page, "Advanced Settings")
    layout.addWidget(owner.tabsServerSettings, 1)

    owner._server_identity_loading = False
    owner._server_identity_baseline = {}
    owner._server_identity_password_configured = False
    owner._server_discord_chat_webhook_configured = False
    owner._server_discord_admin_webhook_configured = False
    owner._server_identity_dirty = False
    owner._server_settings_apply_notice = ""
    owner._server_settings_apply_notice_kind = "success"
    owner.lblServerIdentityState = InlineNotice(
        "Refresh to load the current Server Settings."
    )

    general_layout.addWidget(
        _field_help(
            "Set how the server appears to players. Public visibility controls listing; "
            "it does not open firewall or router ports."
        )
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
    general_layout.addWidget(identity_group)
    general_layout.addStretch(1)

    access_layout.addWidget(
        _field_help(
            "Admins receive management permissions, super admins receive the highest "
            "privilege level, and the whitelist limits who may join when used by VEIN."
        )
    )
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
    access_layout.addWidget(access_group)
    access_layout.addStretch(1)

    gameplay_layout.addWidget(
        InlineNotice(
            "Gameplay changes affect the next server session. Review them together and "
            "restart the server after applying."
        )
    )
    gameplay_group = QtWidgets.QGroupBox("Gameplay Rules")
    gameplay_form = QtWidgets.QFormLayout(gameplay_group)
    owner.chkServerGameplayPvp = QtWidgets.QCheckBox("Allow player-versus-player damage")
    owner.chkServerGameplayVac = QtWidgets.QCheckBox("Enable Steam VAC protection")
    owner.chkServerGameplayAiSpawner = QtWidgets.QCheckBox("Enable AI spawning")
    owner.chkServerGameplayScoreboardBadges = QtWidgets.QCheckBox(
        "Show admin badges on the scoreboard"
    )
    owner.spinServerGameplayTimeMultiplier = QtWidgets.QDoubleSpinBox()
    owner.spinServerGameplayTimeMultiplier.setRange(0.1, 100.0)
    owner.spinServerGameplayTimeMultiplier.setDecimals(2)
    owner.spinServerGameplayTimeMultiplier.setSingleStep(0.1)
    gameplay_form.addRow(owner.chkServerGameplayPvp)
    gameplay_form.addRow(owner.chkServerGameplayVac)
    gameplay_form.addRow(owner.chkServerGameplayAiSpawner)
    gameplay_form.addRow("World time multiplier", owner.spinServerGameplayTimeMultiplier)
    gameplay_form.addRow(
        "",
        _field_help("1.0 is normal world time; higher values advance world time faster."),
    )
    gameplay_form.addRow(owner.chkServerGameplayScoreboardBadges)
    gameplay_layout.addWidget(gameplay_group)
    gameplay_layout.addStretch(1)

    network_layout.addWidget(
        InlineNotice(
            "These ports must be unique. Router and firewall changes are not made by this "
            "application. The VEIN HTTP API is unauthenticated, so keep it private unless "
            "you have added an appropriate security boundary."
        )
    )
    network_group = QtWidgets.QGroupBox("Server Network")
    network_form = QtWidgets.QFormLayout(network_group)
    owner.edServerNetworkBindAddress = QtWidgets.QLineEdit()
    owner.edServerNetworkBindAddress.setPlaceholderText("0.0.0.0")
    owner.spinServerNetworkGamePort = QtWidgets.QSpinBox()
    owner.spinServerNetworkQueryPort = QtWidgets.QSpinBox()
    owner.spinServerNetworkHttpPort = QtWidgets.QSpinBox()
    for port in (
        owner.spinServerNetworkGamePort,
        owner.spinServerNetworkQueryPort,
        owner.spinServerNetworkHttpPort,
    ):
        port.setRange(1, 65535)
    owner.spinServerNetworkHeartbeat = QtWidgets.QSpinBox()
    owner.spinServerNetworkHeartbeat.setRange(1, 3600)
    owner.spinServerNetworkHeartbeat.setSuffix(" seconds")
    owner.lblServerNetworkBindError = QtWidgets.QLabel()
    owner.lblServerNetworkPortsError = QtWidgets.QLabel()
    for error_label in (
        owner.lblServerNetworkBindError,
        owner.lblServerNetworkPortsError,
    ):
        error_label.setWordWrap(True)
        error_label.setProperty("fieldError", True)
    network_form.addRow("Bind address", owner.edServerNetworkBindAddress)
    network_form.addRow("", owner.lblServerNetworkBindError)
    network_form.addRow("Gameplay port", owner.spinServerNetworkGamePort)
    network_form.addRow("Steam query port", owner.spinServerNetworkQueryPort)
    network_form.addRow("HTTP API port", owner.spinServerNetworkHttpPort)
    network_form.addRow("", owner.lblServerNetworkPortsError)
    network_form.addRow("Heartbeat interval", owner.spinServerNetworkHeartbeat)
    network_layout.addWidget(network_group)
    network_layout.addStretch(1)

    discord_layout.addWidget(
        InlineNotice(
            "These are VEIN Game.ini integrations: game chat and admin reports. App "
            "startup, shutdown, crash, backup, and player notifications use the separate "
            "App notifications webhook on the Setup page."
        )
    )
    discord_group = QtWidgets.QGroupBox("In-game Discord Integrations")
    discord_form = QtWidgets.QFormLayout(discord_group)

    def webhook_row(line_edit: QtWidgets.QLineEdit, button: QtWidgets.QPushButton) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(line_edit, 1)
        row_layout.addWidget(button)
        return row

    owner.edServerDiscordChatWebhook = QtWidgets.QLineEdit()
    owner.edServerDiscordAdminWebhook = QtWidgets.QLineEdit()
    owner.btnServerDiscordChatVisibility = QtWidgets.QPushButton("Show")
    owner.btnServerDiscordAdminVisibility = QtWidgets.QPushButton("Show")
    owner.lblServerDiscordChatStatus = QtWidgets.QLabel(
        "Game chat webhook status will appear after Refresh."
    )
    owner.lblServerDiscordAdminStatus = QtWidgets.QLabel(
        "Admin reports webhook status will appear after Refresh."
    )
    for line_edit, button in (
        (owner.edServerDiscordChatWebhook, owner.btnServerDiscordChatVisibility),
        (owner.edServerDiscordAdminWebhook, owner.btnServerDiscordAdminVisibility),
    ):
        line_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        line_edit.setPlaceholderText("Leave blank to preserve the current webhook")
        button.setCheckable(True)
        button.toggled.connect(
            lambda visible, field=line_edit, toggle=button: (
                field.setEchoMode(
                    QtWidgets.QLineEdit.Normal if visible else QtWidgets.QLineEdit.Password
                ),
                toggle.setText("Hide" if visible else "Show"),
            )
        )
    owner.lblServerDiscordChatError = QtWidgets.QLabel()
    owner.lblServerDiscordAdminError = QtWidgets.QLabel()
    for error_label in (
        owner.lblServerDiscordChatError,
        owner.lblServerDiscordAdminError,
    ):
        error_label.setWordWrap(True)
        error_label.setProperty("fieldError", True)
    discord_form.addRow(
        "Game chat webhook",
        webhook_row(owner.edServerDiscordChatWebhook, owner.btnServerDiscordChatVisibility),
    )
    discord_form.addRow("", owner.lblServerDiscordChatStatus)
    discord_form.addRow("", owner.lblServerDiscordChatError)
    discord_form.addRow(
        "Admin reports webhook",
        webhook_row(owner.edServerDiscordAdminWebhook, owner.btnServerDiscordAdminVisibility),
    )
    discord_form.addRow("", owner.lblServerDiscordAdminStatus)
    discord_form.addRow("", owner.lblServerDiscordAdminError)
    discord_layout.addWidget(discord_group)
    discord_layout.addStretch(1)

    owner.btnServerIdentityReset = QtWidgets.QPushButton("Discard Changes")
    owner.btnServerIdentityApply = QtWidgets.QPushButton("Apply Changes")
    for button in (
        owner.btnServerIdentityReset,
        owner.btnServerIdentityApply,
    ):
        button.setEnabled(False)
    set_button_role(owner.btnServerIdentityReset, BUTTON_SECONDARY)
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
        owner.chkServerGameplayPvp,
        owner.chkServerGameplayVac,
        owner.chkServerGameplayAiSpawner,
        owner.spinServerGameplayTimeMultiplier,
        owner.chkServerGameplayScoreboardBadges,
        owner.edServerNetworkBindAddress,
        owner.spinServerNetworkGamePort,
        owner.spinServerNetworkQueryPort,
        owner.spinServerNetworkHttpPort,
        owner.spinServerNetworkHeartbeat,
        owner.edServerDiscordChatWebhook,
        owner.edServerDiscordAdminWebhook,
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
            "Advanced Settings exposes the allowlisted INI table. Use the focused tabs "
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

    owner.frmServerSettingsActions = QtWidgets.QFrame()
    owner.frmServerSettingsActions.setProperty("settingsActionBar", True)
    shared_actions_layout = QtWidgets.QVBoxLayout(owner.frmServerSettingsActions)
    shared_actions_layout.setContentsMargins(8, 8, 8, 8)
    shared_actions_layout.setSpacing(8)
    shared_actions_layout.addWidget(owner.lblServerIdentityState)
    owner.lblServerSettingsApplyHint = _field_help(
        "Apply reviews changes from every marked tab, then creates a timestamped "
        "backup and validates the files after confirmation; restart the server afterward."
    )
    shared_actions_layout.addWidget(owner.lblServerSettingsApplyHint)
    identity_actions = QtWidgets.QHBoxLayout()
    identity_actions.addWidget(owner.btnServerIdentityReset)
    identity_actions.addStretch(1)
    identity_actions.addWidget(owner.btnServerIdentityApply)
    shared_actions_layout.addLayout(identity_actions)
    layout.addWidget(owner.frmServerSettingsActions)

    def update_shared_action_visibility(index: int) -> None:
        curated = index < owner.tabsServerSettings.count() - 1
        owner.frmServerSettingsActions.setVisible(curated)

    owner.tabsServerSettings.currentChanged.connect(
        update_shared_action_visibility
    )
    update_shared_action_visibility(owner.tabsServerSettings.currentIndex())

    return widget
