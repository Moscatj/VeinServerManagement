from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from Tools.server_config_editor import ServerConfigEdit, make_edit
from Tools.server_config_preview import CONSOLE_VARIABLES_SECTION, GAME_STATE_SECTION, SERVER_SETTINGS_SECTION
from Tools.server_config_validator import (
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
)


DEFAULT_SERVER_ROOT = "Server"
DEFAULT_STEAMCMD_PATH = "SteamCMD/steamcmd.exe"
DEFAULT_SAVE_FILENAMES = ("Server.vns", "Server.sav")
DEFAULT_EXECUTABLES = (
    "Vein/Binaries/Win64/VeinServer.exe",
    "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
)
DEFAULT_EXTRA_LAUNCH_ARGS = ("-SteamSockets", "-log")


@dataclass(frozen=True)
class QuickStartIssue:
    field: str
    severity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class QuickStartPlan:
    config_updates: dict[str, Any]
    server_config_edits: tuple[ServerConfigEdit, ...]
    issues: tuple[QuickStartIssue, ...]

    @property
    def can_apply(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_updates": self.config_updates,
            "server_config_edits": [edit.as_dict() for edit in self.server_config_edits],
            "issues": [issue.as_dict() for issue in self.issues],
            "can_apply": self.can_apply,
        }


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_required_int(value: Any, default: int, *, field: str, issues: list[QuickStartIssue]) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        issues.append(QuickStartIssue(field, "ERROR", f"{field} must be numeric."))
        return default


def _positive_int(value: Any, default: int, *, field: str, issues: list[QuickStartIssue]) -> int:
    number = _parse_required_int(value, default, field=field, issues=issues)
    if number < 1:
        issues.append(QuickStartIssue(field, "ERROR", f"{field} must be greater than zero."))
        return default
    return number


def _port(value: Any, default: int, *, field: str, issues: list[QuickStartIssue]) -> int:
    port = _parse_required_int(value, default, field=field, issues=issues)
    if port < 1 or port > 65535:
        issues.append(QuickStartIssue(field, "ERROR", f"{field} must be between 1 and 65535."))
        return default
    return port


def _strings(values: Any) -> tuple[str, ...]:
    if values in (None, ""):
        return ()
    if isinstance(values, str):
        return (values.strip(),) if values.strip() else ()
    if not isinstance(values, Sequence):
        return (str(values).strip(),)
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            output.append(text)
    return tuple(output)


def _optional_webhook(value: Any, *, field: str, issues: list[QuickStartIssue]) -> str:
    url = _text(value)
    if not url:
        return ""
    lowered = url.lower()
    if lowered.startswith("env:"):
        issues.append(
            QuickStartIssue(
                field,
                "ERROR",
                "Vein Game.ini Discord chat integration requires the actual webhook URL, not an ENV: reference.",
            )
        )
    elif not lowered.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        issues.append(
            QuickStartIssue(
                field,
                "WARN",
                "Discord webhook should be an ENV: reference or a Discord webhook URL.",
            )
        )
    return url


def _subpath(server_root: str, *parts: str) -> str:
    root = Path(server_root)
    for part in parts:
        root /= part
    return root.as_posix()


def _configured_executable_warning(server_root: str, executables: Sequence[str]) -> QuickStartIssue | None:
    root = Path(server_root)
    if not root.is_absolute() or not root.exists():
        return QuickStartIssue(
            "server_root",
            "WARN",
            "Server root is not present yet; install the dedicated server before final preflight.",
        )
    if any((root / exe).is_file() for exe in executables):
        return None
    return QuickStartIssue(
        "server_executables",
        "WARN",
        "No configured server executable was found under the selected server root.",
    )


def build_quick_start_plan(values: Mapping[str, Any]) -> QuickStartPlan:
    """Build a preview-only first-run setup plan.

    The plan is intentionally side-effect free. Consumers can show the proposed
    management config updates and pass server_config_edits through the guarded
    server_config_editor preview/apply functions.
    """
    issues: list[QuickStartIssue] = []

    server_root = _text(values.get("server_root") or values.get("server_dir"), DEFAULT_SERVER_ROOT)
    steamcmd_path = _text(values.get("steamcmd_path"), DEFAULT_STEAMCMD_PATH)
    server_name = _text(values.get("server_name"))
    server_description = _text(values.get("server_description"))
    password = _text(values.get("password"))
    public_server = _bool(values.get("public"), True)
    pvp_enabled = _bool(values.get("pvp_enabled"), True)
    bind_addr = _text(values.get("bind_addr") or values.get("multi_home_ip"), "0.0.0.0")
    vac_enabled = _bool(values.get("vac_enabled"), False)
    show_scoreboard_badges = _bool(values.get("show_scoreboard_badges"), True)

    if not server_name:
        issues.append(QuickStartIssue("server_name", "ERROR", "Server name is required."))

    max_players = _positive_int(values.get("max_players"), 8, field="max_players", issues=issues)
    game_port = _port(values.get("game_port"), 7777, field="game_port", issues=issues)
    query_port = _port(values.get("query_port"), 27015, field="query_port", issues=issues)
    http_port = _port(values.get("http_port"), 8080, field="http_port", issues=issues)

    save_dir = _text(values.get("save_dir"), _subpath(server_root, "Vein", "Saved", "SaveGames"))
    logs_dir = _text(values.get("logs_dir"), _subpath(server_root, "Vein", "Saved", "Logs"))
    absolute_log_file = _text(values.get("absolute_log_file"), _subpath(logs_dir, "Vein.log"))
    backup_root = _text(values.get("backup_root"), "Backups")
    save_filenames = _strings(values.get("save_filenames")) or DEFAULT_SAVE_FILENAMES
    admin_ids = _strings(values.get("admin_steam_ids"))
    super_admin_ids = _strings(values.get("super_admin_steam_ids"))
    whitelist_ids = _strings(values.get("whitelisted_players"))
    discord_chat_webhook = _optional_webhook(values.get("discord_chat_webhook_url"), field="discord_chat_webhook_url", issues=issues)
    discord_admin_webhook = _optional_webhook(
        values.get("discord_chat_admin_webhook_url"),
        field="discord_chat_admin_webhook_url",
        issues=issues,
    )
    heartbeat_interval = _positive_int(
        values.get("heartbeat_interval"),
        5,
        field="heartbeat_interval",
        issues=issues,
    )

    executables = _strings(values.get("server_executables")) or DEFAULT_EXECUTABLES
    preferred_exe = _text(values.get("preferred_exe"), executables[0])
    extra_launch_args = _strings(values.get("extra_launch_args")) or DEFAULT_EXTRA_LAUNCH_ARGS
    exe_warning = _configured_executable_warning(server_root, executables)
    if exe_warning is not None:
        issues.append(exe_warning)

    http_api_enabled = _bool(values.get("http_api_enabled"), True)
    if http_api_enabled:
        issues.append(
            QuickStartIssue(
                "http_api",
                "WARN",
                "Vein HTTP API has no built-in authentication; keep it local or behind an operator-controlled proxy.",
            )
        )

    config_updates: dict[str, Any] = {
        "paths": {
            "server_root": server_root,
            "saves_dir": save_dir,
            "logs_dir": logs_dir,
            "absolute_log_file": absolute_log_file,
            "runtime_dir": _text(values.get("runtime_dir"), "Runtime"),
            "mgmt_log_dir": _text(values.get("mgmt_log_dir"), "Logs"),
        },
        "server": {
            "executables": list(executables),
            "preferred_exe": preferred_exe,
            "game_port": game_port,
            "query_port": query_port,
            "max_players": max_players,
            "multi_home_ip": bind_addr,
            "enable_query_port": True,
            "extra_launch_args": list(extra_launch_args),
        },
        "http_api": {
            "enabled": http_api_enabled,
            "host": _text(values.get("http_api_host"), "127.0.0.1"),
            "port": http_port,
        },
        "steam": {
            "steamcmd_path": steamcmd_path,
            "app_id": _int(values.get("steam_app_id"), 2131400),
        },
        "backups": {
            "root": backup_root,
            "save_filenames": list(save_filenames),
        },
        "discord": {
            "defaults": {
                "server_name": server_name or "Your Vein Server",
            }
        },
    }

    edits: list[ServerConfigEdit] = [
        make_edit("Game.ini", ENGINE_GAME_SESSION_SECTION, "MaxPlayers", str(max_players)),
        make_edit("Game.ini", GAME_INI_SECTION, "ServerName", server_name),
        make_edit("Game.ini", GAME_INI_SECTION, "bPublic", "True" if public_server else "False"),
        make_edit("Game.ini", GAME_INI_SECTION, "BindAddr", bind_addr),
        make_edit("Game.ini", GAME_INI_SECTION, "HeartbeatInterval", str(heartbeat_interval)),
        make_edit("Game.ini", GAME_INI_SECTION, "HTTPPort", str(http_port)),
        make_edit("Game.ini", ONLINE_STEAM_SECTION, "GameServerQueryPort", str(query_port)),
        make_edit("Game.ini", ONLINE_STEAM_SECTION, "bVACEnabled", "1" if vac_enabled else "0"),
        make_edit("Game.ini", URL_SECTION, "Port", str(game_port)),
        make_edit(
            "Game.ini",
            SERVER_SETTINGS_SECTION,
            "GS_ShowScoreboardBadges",
            "1" if show_scoreboard_badges else "0",
        ),
        make_edit("Engine.ini", CONSOLE_VARIABLES_SECTION, "vein.PvP", "True" if pvp_enabled else "False"),
    ]
    if server_description:
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "ServerDescription", server_description))
    if password:
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "Password", password))
    if admin_ids:
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "AdminSteamIDs", admin_ids))
    if super_admin_ids:
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "SuperAdminSteamIDs", super_admin_ids))
    if whitelist_ids:
        edits.append(make_edit("Game.ini", GAME_STATE_SECTION, "WhitelistedPlayers", whitelist_ids))
    if discord_chat_webhook:
        edits.append(make_edit("Game.ini", SERVER_SETTINGS_SECTION, "DiscordChatWebhookURL", f'"{discord_chat_webhook}"'))
    if discord_admin_webhook:
        edits.append(
            make_edit(
                "Game.ini",
                SERVER_SETTINGS_SECTION,
                "DiscordChatAdminWebhookURL",
                f'"{discord_admin_webhook}"',
            )
        )

    return QuickStartPlan(
        config_updates=config_updates,
        server_config_edits=tuple(edits),
        issues=tuple(issues),
    )
