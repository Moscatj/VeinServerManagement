from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from Tools.server_config_editor import ServerConfigEdit, apply_server_config_edits, make_edit
from Tools.server_config_preview import CONSOLE_VARIABLES_SECTION, GAME_STATE_SECTION, SERVER_SETTINGS_SECTION
from Tools.server_config_validator import ServerConfigCheck, read_unreal_ini, server_config_paths
from Tools.server_config_validator import (
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "Config" / "config.yaml"
DEFAULT_CONFIG_TEMPLATE = PROJECT_ROOT / "Config" / "config.example.yaml"
DEFAULT_CONFIG_BACKUP_ROOT = PROJECT_ROOT / "Backups" / "ConfigEdits" / "ManagementConfig"
DEFAULT_SERVER_ROOT = "Server"
DEFAULT_STEAMCMD_PATH = "SteamCMD/steamcmd.exe"
DEFAULT_SAVE_FILENAMES = ("Server.vns", "Server.sav")
DEFAULT_EXECUTABLES = (
    "Vein/Binaries/Win64/VeinServer.exe",
    "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
)
DEFAULT_EXTRA_LAUNCH_ARGS = ("-SteamSockets", "-log")
NEW_SERVER_MODE = "new"
EXISTING_SERVER_MODE = "existing"
QUICK_START_MODES = {NEW_SERVER_MODE, EXISTING_SERVER_MODE}


@dataclass(frozen=True)
class ExistingServerSettings:
    server_root: str
    values: dict[str, Any]
    loaded_fields: tuple[str, ...]
    missing_files: tuple[str, ...]
    password_configured: bool | None = None
    discord_chat_webhook_configured: bool | None = None
    discord_admin_webhook_configured: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ServerRootInspection:
    state: str
    server_root: str
    indicators: tuple[str, ...]

    @property
    def is_existing_server(self) -> bool:
        return self.state == "existing"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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


@dataclass(frozen=True)
class QuickStartApplyResult:
    plan: QuickStartPlan
    config_path: str
    config_backup: str
    config_changed: bool
    server_config_applied: bool
    server_config_result: dict[str, Any] | None
    validation: tuple[ServerConfigCheck, ...]
    messages: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.as_dict(),
            "config_path": self.config_path,
            "config_backup": self.config_backup,
            "config_changed": self.config_changed,
            "server_config_applied": self.server_config_applied,
            "server_config_result": self.server_config_result,
            "validation": [item.as_dict() for item in self.validation],
            "messages": list(self.messages),
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


def _first_ini_value(
    sections: Mapping[str, Mapping[str, Sequence[str]]],
    section: str,
    key: str,
) -> str | None:
    values = sections.get(section, {}).get(key, ())
    return str(values[0]) if values else None


def _all_ini_values(
    sections: Mapping[str, Mapping[str, Sequence[str]]],
    section: str,
    key: str,
) -> list[str] | None:
    values = sections.get(section, {}).get(key)
    return [str(value) for value in values] if values else None


def inspect_server_root(
    server_root: str | Path,
    executables: Sequence[str] | None = None,
) -> ServerRootInspection:
    """Classify a proposed server destination without modifying it."""
    root = Path(server_root).expanduser()
    if not root.exists():
        return ServerRootInspection("missing", str(root), ())
    if not root.is_dir():
        return ServerRootInspection("occupied", str(root), (str(root),))

    candidates = tuple(executables or DEFAULT_EXECUTABLES)
    paths = server_config_paths(root)
    indicators = tuple(
        str(path)
        for path in (
            *(root / executable for executable in candidates),
            paths["game_ini"],
            paths["engine_ini"],
        )
        if path.is_file()
    )
    if indicators:
        return ServerRootInspection("existing", str(root), indicators)
    try:
        occupied = any(root.iterdir())
    except OSError:
        occupied = True
    return ServerRootInspection("occupied" if occupied else "empty", str(root), ())


def load_existing_server_settings(
    server_root: str | Path,
    executables: Sequence[str] | None = None,
) -> ExistingServerSettings:
    """Read supported, non-secret Quick Start values from an existing server."""
    candidates = tuple(executables or DEFAULT_EXECUTABLES)
    inspection = inspect_server_root(server_root, candidates)
    root = Path(inspection.server_root)
    if not root.is_dir():
        raise ValueError(f"Existing server root was not found: {root}")
    if not inspection.is_existing_server:
        raise ValueError(f"No Vein server executable or server config file was found under: {root}")

    paths = server_config_paths(root)
    ini_paths = (paths["game_ini"], paths["engine_ini"])
    missing = tuple(str(path) for path in ini_paths if not path.is_file())
    game = read_unreal_ini(paths["game_ini"]) if paths["game_ini"].is_file() else {}
    engine = read_unreal_ini(paths["engine_ini"]) if paths["engine_ini"].is_file() else {}

    values: dict[str, Any] = {"setup_mode": EXISTING_SERVER_MODE, "server_root": str(root)}
    mappings = (
        ("server_name", game, GAME_INI_SECTION, "ServerName", str),
        ("server_description", game, GAME_INI_SECTION, "ServerDescription", str),
        ("max_players", game, ENGINE_GAME_SESSION_SECTION, "MaxPlayers", int),
        ("game_port", game, URL_SECTION, "Port", int),
        ("query_port", game, ONLINE_STEAM_SECTION, "GameServerQueryPort", int),
        ("http_port", game, GAME_INI_SECTION, "HTTPPort", int),
        ("bind_addr", game, GAME_INI_SECTION, "BindAddr", str),
        ("heartbeat_interval", game, GAME_INI_SECTION, "HeartbeatInterval", int),
        ("public", game, GAME_INI_SECTION, "bPublic", lambda value: _bool(value, True)),
        ("vac_enabled", game, ONLINE_STEAM_SECTION, "bVACEnabled", lambda value: _bool(value, False)),
        (
            "show_scoreboard_badges",
            game,
            SERVER_SETTINGS_SECTION,
            "GS_ShowScoreboardBadges",
            lambda value: _bool(value, True),
        ),
        ("pvp_enabled", engine, CONSOLE_VARIABLES_SECTION, "vein.PvP", lambda value: _bool(value, True)),
    )
    for field, sections, section, key, convert in mappings:
        raw = _first_ini_value(sections, section, key)
        if raw is None:
            continue
        try:
            values[field] = convert(raw)
        except (TypeError, ValueError):
            continue

    list_mappings = (
        ("admin_steam_ids", GAME_INI_SECTION, "AdminSteamIDs"),
        ("super_admin_steam_ids", GAME_INI_SECTION, "SuperAdminSteamIDs"),
        ("whitelisted_players", GAME_STATE_SECTION, "WhitelistedPlayers"),
    )
    for field, section, key in list_mappings:
        existing = _all_ini_values(game, section, key)
        if existing is not None:
            values[field] = existing

    # Passwords and webhook URLs are deliberately not loaded into GUI fields.
    password_value = _first_ini_value(game, GAME_INI_SECTION, "Password")
    password_configured = bool(password_value) if paths["game_ini"].is_file() else None
    chat_webhook = _first_ini_value(
        game, SERVER_SETTINGS_SECTION, "DiscordChatWebhookURL"
    )
    admin_webhook = _first_ini_value(
        game, SERVER_SETTINGS_SECTION, "DiscordChatAdminWebhookURL"
    )
    chat_webhook_configured = bool(chat_webhook) if paths["game_ini"].is_file() else None
    admin_webhook_configured = bool(admin_webhook) if paths["game_ini"].is_file() else None
    loaded = tuple(sorted(key for key in values if key not in {"setup_mode", "server_root"}))
    return ExistingServerSettings(
        str(root),
        values,
        loaded,
        missing,
        password_configured,
        chat_webhook_configured,
        admin_webhook_configured,
    )


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
    if not root.is_dir():
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


def _deep_merge(base: Mapping[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(dict(base))
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return dict(data)


def _config_template_for(path: Path) -> Path | None:
    if path.exists():
        return None
    if DEFAULT_CONFIG_TEMPLATE.exists():
        return DEFAULT_CONFIG_TEMPLATE
    return None


def _backup_file(path: Path, backup_root: Path = DEFAULT_CONFIG_BACKUP_ROOT) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"{path.stem}-{stamp}{path.suffix or '.bak'}"
    if path.exists():
        backup.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    else:
        backup.write_text("", encoding="utf-8")
    return str(backup)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _dump_yaml(data: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=False)


def _server_config_runtime_cfg(plan: QuickStartPlan) -> dict[str, Any]:
    updates = plan.config_updates
    paths = updates.get("paths", {})
    server = updates.get("server", {})
    http_api = updates.get("http_api", {})
    return {
        "server_dir": paths.get("server_root", DEFAULT_SERVER_ROOT),
        "server_executables": server.get("executables", list(DEFAULT_EXECUTABLES)),
        "game_port": server.get("game_port", 7777),
        "query_port": server.get("query_port", 27015),
        "max_players": server.get("max_players", 8),
        "http_api": http_api,
    }


def _server_root_exists(plan: QuickStartPlan) -> bool:
    root = Path(str(plan.config_updates.get("paths", {}).get("server_root", ""))).expanduser()
    return root.is_dir()


def build_quick_start_plan(values: Mapping[str, Any]) -> QuickStartPlan:
    """Build a preview-only first-run setup plan.

    The plan is intentionally side-effect free. Consumers can show the proposed
    management config updates and pass server_config_edits through the guarded
    server_config_editor preview/apply functions.
    """
    issues: list[QuickStartIssue] = []

    setup_mode = _text(values.get("setup_mode"), NEW_SERVER_MODE).lower()
    if setup_mode not in QUICK_START_MODES:
        issues.append(QuickStartIssue("setup_mode", "ERROR", "Choose New Server or Existing Server."))
        setup_mode = NEW_SERVER_MODE
    selected_fields = set(_strings(values.get("server_config_fields")))

    def should_edit(field: str) -> bool:
        return setup_mode == NEW_SERVER_MODE or field in selected_fields

    server_root = _text(values.get("server_root") or values.get("server_dir"), DEFAULT_SERVER_ROOT)
    if setup_mode == EXISTING_SERVER_MODE:
        loaded_root = _text(values.get("existing_loaded_root"))
        if not loaded_root or Path(loaded_root).expanduser() != Path(server_root).expanduser():
            issues.append(
                QuickStartIssue(
                    "server_root",
                    "ERROR",
                    "Load settings from the selected existing server folder before building the preview.",
                )
            )
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
        if setup_mode == EXISTING_SERVER_MODE:
            issues.append(QuickStartIssue(exe_warning.field, "ERROR", exe_warning.message))
        else:
            issues.append(exe_warning)
    if setup_mode == NEW_SERVER_MODE:
        destination = inspect_server_root(server_root, executables)
        if destination.is_existing_server:
            issues.append(
                QuickStartIssue(
                    "server_root",
                    "ERROR",
                    "A Vein server already exists in this folder. Switch to Existing Server mode.",
                )
            )
        elif destination.state == "occupied":
            issues.append(
                QuickStartIssue(
                    "server_root",
                    "ERROR",
                    "New Server requires a missing or empty destination folder.",
                )
            )

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
            "ports": {
                "game": game_port,
                "query": query_port,
                "bind_ip": bind_addr,
            },
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

    edits: list[ServerConfigEdit] = []
    scalar_edits = (
        ("max_players", "Game.ini", ENGINE_GAME_SESSION_SECTION, "MaxPlayers", str(max_players)),
        ("server_name", "Game.ini", GAME_INI_SECTION, "ServerName", server_name),
        ("public", "Game.ini", GAME_INI_SECTION, "bPublic", "True" if public_server else "False"),
        ("bind_addr", "Game.ini", GAME_INI_SECTION, "BindAddr", bind_addr),
        ("heartbeat_interval", "Game.ini", GAME_INI_SECTION, "HeartbeatInterval", str(heartbeat_interval)),
        ("http_port", "Game.ini", GAME_INI_SECTION, "HTTPPort", str(http_port)),
        ("query_port", "Game.ini", ONLINE_STEAM_SECTION, "GameServerQueryPort", str(query_port)),
        ("vac_enabled", "Game.ini", ONLINE_STEAM_SECTION, "bVACEnabled", "1" if vac_enabled else "0"),
        ("game_port", "Game.ini", URL_SECTION, "Port", str(game_port)),
        (
            "show_scoreboard_badges",
            "Game.ini",
            SERVER_SETTINGS_SECTION,
            "GS_ShowScoreboardBadges",
            "1" if show_scoreboard_badges else "0",
        ),
        ("pvp_enabled", "Engine.ini", CONSOLE_VARIABLES_SECTION, "vein.PvP", "True" if pvp_enabled else "False"),
    )
    for field, source, section, key, value in scalar_edits:
        if should_edit(field):
            edits.append(make_edit(source, section, key, value))

    if should_edit("server_description") and (server_description or setup_mode == EXISTING_SERVER_MODE):
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "ServerDescription", server_description))
    if should_edit("password") and (password or setup_mode == EXISTING_SERVER_MODE):
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "Password", password))
    if should_edit("admin_steam_ids") and (admin_ids or setup_mode == EXISTING_SERVER_MODE):
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "AdminSteamIDs", admin_ids))
    if should_edit("super_admin_steam_ids") and (super_admin_ids or setup_mode == EXISTING_SERVER_MODE):
        edits.append(make_edit("Game.ini", GAME_INI_SECTION, "SuperAdminSteamIDs", super_admin_ids))
    if should_edit("whitelisted_players") and (whitelist_ids or setup_mode == EXISTING_SERVER_MODE):
        edits.append(make_edit("Game.ini", GAME_STATE_SECTION, "WhitelistedPlayers", whitelist_ids))
    if should_edit("discord_chat_webhook_url") and (discord_chat_webhook or setup_mode == EXISTING_SERVER_MODE):
        webhook_value = f'"{discord_chat_webhook}"' if discord_chat_webhook else ""
        edits.append(make_edit("Game.ini", SERVER_SETTINGS_SECTION, "DiscordChatWebhookURL", webhook_value))
    if should_edit("discord_chat_admin_webhook_url") and (discord_admin_webhook or setup_mode == EXISTING_SERVER_MODE):
        webhook_value = f'"{discord_admin_webhook}"' if discord_admin_webhook else ""
        edits.append(
            make_edit(
                "Game.ini",
                SERVER_SETTINGS_SECTION,
                "DiscordChatAdminWebhookURL",
                webhook_value,
            )
        )

    return QuickStartPlan(
        config_updates=config_updates,
        server_config_edits=tuple(edits),
        issues=tuple(issues),
    )


def apply_quick_start_plan(
    values: Mapping[str, Any],
    *,
    config_path: str | Path | None = None,
    apply_server_config: bool = True,
    config_backup_root: str | Path | None = None,
    server_config_backup_root: str | Path | None = None,
) -> QuickStartApplyResult:
    """Apply Quick Start updates through guarded local writers.

    The management config is written locally. Game config edits are delegated to
    server_config_editor, which creates backups and validates after writing. If
    the selected server root does not exist yet, game config writes are skipped
    so Quick Start does not create fake dedicated-server folders.
    """
    plan = build_quick_start_plan(values)
    if not plan.can_apply:
        raise ValueError("Quick Start plan has blocking errors.")

    target = Path(config_path or DEFAULT_CONFIG_PATH).expanduser()
    template = _config_template_for(target)
    base = _load_yaml_mapping(template or target)
    merged = _deep_merge(base, plan.config_updates)
    before = _dump_yaml(base)
    after = _dump_yaml(merged)
    backup = _backup_file(target, Path(config_backup_root).expanduser() if config_backup_root else DEFAULT_CONFIG_BACKUP_ROOT)
    config_changed = before != after or not target.exists()
    if config_changed:
        _atomic_write(target, after)

    messages: list[str] = []
    server_result: dict[str, Any] | None = None
    validation: tuple[ServerConfigCheck, ...] = ()
    server_config_applied = False
    runtime_cfg = _server_config_runtime_cfg(plan)
    if apply_server_config:
        if _server_root_exists(plan):
            result = apply_server_config_edits(
                runtime_cfg,
                plan.server_config_edits,
                backup_root=Path(server_config_backup_root).expanduser() if server_config_backup_root else None,
            )
            server_result = result.as_dict()
            validation = result.validation
            server_config_applied = True
        else:
            messages.append(
                "Skipped Game.ini/Engine.ini writes because the selected server root does not exist yet."
            )

    return QuickStartApplyResult(
        plan=plan,
        config_path=str(target),
        config_backup=backup,
        config_changed=config_changed,
        server_config_applied=server_config_applied,
        server_config_result=server_result,
        validation=validation,
        messages=tuple(messages),
    )
