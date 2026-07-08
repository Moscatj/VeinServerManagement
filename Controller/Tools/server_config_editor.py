from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from Tools.server_config_preview import (
    CONSOLE_VARIABLES_SECTION,
    GAME_STATE_SECTION,
    SERVER_SETTINGS_SECTION,
)
from Tools.server_config_validator import (
    CORE_LOG_SECTION,
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
    ServerConfigCheck,
    server_config_paths,
    validate_server_config,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "Backups" / "ConfigEdits"

DUPLICATE_KEY_ALLOWLIST = {
    "AdminSteamIDs",
    "SuperAdminSteamIDs",
    "WhitelistedPlayers",
}

GAME_INI_ALLOWLIST = {
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
}

ENGINE_INI_ALLOWLIST = {
    (CONSOLE_VARIABLES_SECTION, "vein.PvP"),
    (CONSOLE_VARIABLES_SECTION, "vein.AISpawner.Enabled"),
    (CONSOLE_VARIABLES_SECTION, "vein.TimeMultiplier"),
    (CORE_LOG_SECTION, "LogOnline"),
    (CORE_LOG_SECTION, "LogOnlineSession"),
}

ALLOWLIST = {
    "Game.ini": GAME_INI_ALLOWLIST,
    "Engine.ini": ENGINE_INI_ALLOWLIST,
}


@dataclass(frozen=True)
class ServerConfigEdit:
    source: str
    section: str
    key: str
    values: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ServerConfigEditPlan:
    diffs: dict[str, str]
    changed_files: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ServerConfigEditResult:
    diffs: dict[str, str]
    changed_files: tuple[str, ...]
    backups: tuple[str, ...]
    validation: tuple[ServerConfigCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validation"] = [item.as_dict() for item in self.validation]
        return payload


def _path_from_value(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value)).expanduser()


def _normalize_source(source: str) -> str:
    name = Path(str(source)).name
    if name not in {"Game.ini", "Engine.ini"}:
        raise ValueError(f"Unsupported server config file: {source}")
    return name


def _normalize_values(values: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        vals = (values,)
    else:
        vals = tuple(str(value) for value in values)
    for value in vals:
        if "\n" in value or "\r" in value:
            raise ValueError("Config values may not contain newlines.")
    return vals


def make_edit(source: str, section: str, key: str, values: str | Sequence[str]) -> ServerConfigEdit:
    normalized_source = _normalize_source(source)
    edit = ServerConfigEdit(
        normalized_source,
        str(section).strip(),
        str(key).strip(),
        _normalize_values(values),
    )
    _validate_edit(edit)
    return edit


def _validate_edit(edit: ServerConfigEdit) -> None:
    allowed = ALLOWLIST.get(edit.source, set())
    if (edit.section, edit.key) not in allowed:
        raise ValueError(f"{edit.source} key is not editable: [{edit.section}] {edit.key}")
    if not edit.section or not edit.key:
        raise ValueError("Config section and key are required.")
    if len(edit.values) > 1 and edit.key not in DUPLICATE_KEY_ALLOWLIST:
        raise ValueError(f"{edit.key} does not support multiple values.")


def _target_paths(cfg: Mapping[str, Any]) -> dict[str, Path]:
    server_root = _path_from_value(cfg.get("server_dir"))
    if server_root is None:
        raise ValueError("server_dir is required.")
    paths = server_config_paths(server_root)
    return {
        "Game.ini": paths["game_ini"],
        "Engine.ini": paths["engine_ini"],
    }


def _line_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", ";", "[")) or "=" not in stripped:
        return None
    key, _ = stripped.split("=", 1)
    return key.strip().lstrip("+").strip()


def _format_edit_lines(edit: ServerConfigEdit) -> list[str]:
    prefix = "+" if edit.key in DUPLICATE_KEY_ALLOWLIST and len(edit.values) > 1 else ""
    return [f"{prefix}{edit.key}={value}" for value in edit.values]


def _apply_section_edit(text: str, edit: ServerConfigEdit) -> str:
    lines = text.splitlines()
    output: list[str] = []
    current_section = ""
    section_found = False
    inserted = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if section_found and not inserted:
                output.extend(_format_edit_lines(edit))
                inserted = True
            current_section = stripped[1:-1].strip()
            output.append(line)
            if current_section == edit.section:
                section_found = True
            continue

        if section_found and current_section == edit.section and _line_key(line) == edit.key:
            continue
        output.append(line)

    if section_found and not inserted:
        output.extend(_format_edit_lines(edit))
    elif not section_found:
        if output and output[-1].strip():
            output.append("")
        output.append(f"[{edit.section}]")
        output.extend(_format_edit_lines(edit))

    return "\n".join(output).rstrip() + "\n"


def _diff(original: str, updated: str, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"{path} (current)",
            tofile=f"{path} (proposed)",
        )
    )


def _planned_files(cfg: Mapping[str, Any], edits: Iterable[ServerConfigEdit]) -> dict[Path, tuple[str, str]]:
    paths = _target_paths(cfg)
    grouped: dict[str, list[ServerConfigEdit]] = {}
    for edit in edits:
        _validate_edit(edit)
        grouped.setdefault(edit.source, []).append(edit)

    planned: dict[Path, tuple[str, str]] = {}
    for source, source_edits in grouped.items():
        path = paths[source]
        original = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        updated = original
        for edit in source_edits:
            updated = _apply_section_edit(updated, edit)
        planned[path] = (original, updated)
    return planned


def preview_server_config_edits(
    cfg: Mapping[str, Any],
    edits: Iterable[ServerConfigEdit],
) -> ServerConfigEditPlan:
    diffs: dict[str, str] = {}
    changed: list[str] = []
    for path, (original, updated) in _planned_files(cfg, edits).items():
        if original == updated:
            continue
        changed.append(str(path))
        diffs[str(path)] = _diff(original, updated, path)
    return ServerConfigEditPlan(diffs=diffs, changed_files=tuple(changed))


def _backup_files(paths: Iterable[Path], backup_root: Path) -> tuple[str, ...]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = backup_root / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        target = backup_dir / path.name
        target.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        backups.append(str(target))
    return tuple(backups)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def apply_server_config_edits(
    cfg: Mapping[str, Any],
    edits: Iterable[ServerConfigEdit],
    *,
    backup_root: Path | None = None,
) -> ServerConfigEditResult:
    planned = _planned_files(cfg, edits)
    changed = {path: pair for path, pair in planned.items() if pair[0] != pair[1]}
    if not changed:
        return ServerConfigEditResult(
            diffs={},
            changed_files=(),
            backups=(),
            validation=tuple(validate_server_config(cfg)),
        )

    backup_dir = backup_root or DEFAULT_BACKUP_ROOT
    backups = _backup_files(changed.keys(), backup_dir)
    diffs = {str(path): _diff(original, updated, path) for path, (original, updated) in changed.items()}
    for path, (_, updated) in changed.items():
        _atomic_write(path, updated)

    return ServerConfigEditResult(
        diffs=diffs,
        changed_files=tuple(str(path) for path in changed),
        backups=backups,
        validation=tuple(validate_server_config(cfg)),
    )
