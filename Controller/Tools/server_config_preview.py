from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from Tools.server_config_validator import (
    CORE_LOG_SECTION,
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
    read_unreal_ini,
    server_config_paths,
)

GAME_STATE_SECTION = "/Script/Vein.VeinGameStateBase"
SERVER_SETTINGS_SECTION = "/Script/Vein.ServerSettings"
CONSOLE_VARIABLES_SECTION = "ConsoleVariables"

SECRET_KEYS = {
    "Password",
    "DiscordChatWebhookURL",
    "DiscordChatAdminWebhookURL",
}
SECRET_KEY_MARKERS = ("password", "webhook", "token", "secret")


@dataclass(frozen=True)
class ServerConfigPreviewItem:
    source: str
    section: str
    key: str
    value: str
    present: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def mask_config_value(key: str, value: str) -> str:
    if not value:
        return ""
    lowered_key = key.lower()
    if key in SECRET_KEYS or any(marker in lowered_key for marker in SECRET_KEY_MARKERS):
        return "<configured, masked>"
    lowered = value.lower()
    if "discord.com/api/webhooks/" in lowered:
        return "<discord webhook configured, masked>"
    return value


def _path_from_value(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value)).expanduser()


def _values(
    sections: Mapping[str, Mapping[str, list[str]]],
    section: str,
    key: str,
) -> list[str]:
    return list(sections.get(section, {}).get(key, []))


def _add_item(
    items: list[ServerConfigPreviewItem],
    *,
    source: str,
    sections: Mapping[str, Mapping[str, list[str]]],
    section: str,
    key: str,
) -> None:
    values = _values(sections, section, key)
    if not values:
        items.append(ServerConfigPreviewItem(source, section, key, "(not set)", False))
        return

    display = ", ".join(mask_config_value(key, value) for value in values)
    items.append(ServerConfigPreviewItem(source, section, key, display, True))


def _add_existing_items(
    items: list[ServerConfigPreviewItem],
    *,
    source: str,
    sections: Mapping[str, Mapping[str, list[str]]],
    documented: set[tuple[str, str]],
) -> None:
    for section in sorted(sections):
        for key in sorted(sections[section]):
            if (section, key) in documented:
                continue
            values = sections[section].get(key) or []
            display = ", ".join(mask_config_value(key, value) for value in values)
            items.append(ServerConfigPreviewItem(source, section, key, display, True))


def build_server_config_preview(cfg: Mapping[str, Any]) -> dict[str, Any]:
    server_root = _path_from_value(cfg.get("server_dir"))
    if server_root is None:
        return {
            "server_root": "",
            "game_ini": "",
            "engine_ini": "",
            "items": [],
            "missing_files": ["Server root is not configured."],
        }

    paths = server_config_paths(server_root)
    game_ini = paths["game_ini"]
    engine_ini = paths["engine_ini"]
    missing_files: list[str] = []
    items: list[ServerConfigPreviewItem] = []

    game_sections: dict[str, dict[str, list[str]]] = {}
    if game_ini.is_file():
        game_sections = read_unreal_ini(game_ini)
    else:
        missing_files.append(str(game_ini))

    engine_sections: dict[str, dict[str, list[str]]] = {}
    if engine_ini.is_file():
        engine_sections = read_unreal_ini(engine_ini)
    else:
        missing_files.append(str(engine_ini))

    game_keys = [
        (ENGINE_GAME_SESSION_SECTION, "MaxPlayers"),
        (GAME_INI_SECTION, "bPublic"),
        (GAME_INI_SECTION, "ServerName"),
        (GAME_INI_SECTION, "ServerDescription"),
        (GAME_INI_SECTION, "BindAddr"),
        (GAME_INI_SECTION, "SuperAdminSteamIDs"),
        (GAME_INI_SECTION, "AdminSteamIDs"),
        (GAME_INI_SECTION, "HeartbeatInterval"),
        (GAME_INI_SECTION, "Password"),
        (GAME_INI_SECTION, "HTTPPort"),
        (GAME_STATE_SECTION, "WhitelistedPlayers"),
        (ONLINE_STEAM_SECTION, "GameServerQueryPort"),
        (ONLINE_STEAM_SECTION, "bVACEnabled"),
        (URL_SECTION, "Port"),
        (SERVER_SETTINGS_SECTION, "DiscordChatWebhookURL"),
        (SERVER_SETTINGS_SECTION, "DiscordChatAdminWebhookURL"),
        (SERVER_SETTINGS_SECTION, "GS_ShowScoreboardBadges"),
    ]
    documented_game_keys = set(game_keys)
    for section, key in game_keys:
        _add_item(
            items,
            source="Game.ini",
            sections=game_sections,
            section=section,
            key=key,
        )
    _add_existing_items(
        items,
        source="Game.ini",
        sections=game_sections,
        documented=documented_game_keys,
    )

    engine_keys = [
        (CONSOLE_VARIABLES_SECTION, "vein.PvP"),
        (CONSOLE_VARIABLES_SECTION, "vein.AISpawner.Enabled"),
        (CONSOLE_VARIABLES_SECTION, "vein.TimeMultiplier"),
        (CORE_LOG_SECTION, "LogOnline"),
        (CORE_LOG_SECTION, "LogOnlineSession"),
    ]
    documented_engine_keys = set(engine_keys)
    for section, key in engine_keys:
        _add_item(
            items,
            source="Engine.ini",
            sections=engine_sections,
            section=section,
            key=key,
        )
    _add_existing_items(
        items,
        source="Engine.ini",
        sections=engine_sections,
        documented=documented_engine_keys,
    )

    return {
        "server_root": str(server_root),
        "game_ini": str(game_ini),
        "engine_ini": str(engine_ini),
        "items": [item.as_dict() for item in items],
        "missing_files": missing_files,
    }
