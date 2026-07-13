from __future__ import annotations

from pathlib import Path
from typing import List

from config_helper import config, get_path

__all__ = [
    "server_dir",
    "logs_dir",
    "save_dir",
    "save_games_override",
    "absolute_log_file",
    "game_log_file",
    "game_log_override",
    "log_file_candidates",
    "resolve_active_log",
    "save_filenames",
    "resolve_save_file",
]


def server_dir() -> Path:
    return Path(get_path("server_dir"))


def logs_dir() -> Path:
    sd = server_dir()
    return Path(config.get("logs_dir") or (sd / "Vein" / "Saved" / "Logs"))


def save_dir() -> Path:
    sd = server_dir()
    return Path(config.get("save_dir") or (sd / "Vein" / "Saved" / "SaveGames"))


def save_games_override() -> str:
    """Return the advanced SaveGames override, or blank for automatic mode."""
    return str(config.get("save_games_override", "") or "")


def absolute_log_file() -> str:
    """Compatibility name for the resolved Vein game log file."""
    return str(config.get("absolute_log_file", "") or "")


def game_log_file() -> Path:
    """Return the single Vein game log used for launch and monitoring."""
    configured = config.get("game_log_file") or absolute_log_file()
    if configured:
        return Path(str(configured)).expanduser()
    return server_dir() / "Vein" / "Saved" / "Logs" / "Vein.log"


def game_log_override() -> str:
    """Return the advanced override, or blank when automatic derivation is active."""
    return str(config.get("game_log_override", "") or "")


def log_file_candidates() -> List[Path]:
    """Return configured and conventional Vein log paths in priority order."""
    server = server_dir()
    configured_logs = logs_dir()
    candidates = [
        game_log_file(),
        configured_logs / "Vein.log",
        server / "Vein" / "Saved" / "Logs" / "Vein.log",
        server / "Saved" / "Logs" / "Vein.log",
    ]
    unique: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate).casefold()
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def resolve_active_log(*, allow_missing: bool = False) -> Path | None:
    """Find the active Vein log, including logs created after monitor startup.

    Explicit and conventional ``Vein.log`` locations take precedence. If no
    primary file exists, the newest ``*.log`` from the configured/common log
    directories is used. ``allow_missing`` returns the expected primary path
    so callers can wait for a clean server's first log to be created.
    """
    candidates = log_file_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    newest: tuple[float, Path] | None = None
    checked_dirs: set[str] = set()
    for candidate in candidates:
        folder = candidate.parent
        key = str(folder).casefold()
        if key in checked_dirs:
            continue
        checked_dirs.add(key)
        try:
            files = folder.glob("*.log")
            for path in files:
                try:
                    modified = path.stat().st_mtime
                except OSError:
                    continue
                if newest is None or modified > newest[0]:
                    newest = (modified, path)
        except OSError:
            continue

    if newest is not None:
        return newest[1]
    return candidates[0] if allow_missing and candidates else None


def save_filenames() -> List[str]:
    return list(config.get("save_filenames", ["Server.vns", "Server.sav"]))


def resolve_save_file() -> Path:
    sdir = save_dir()
    names = save_filenames()
    for name in names:
        p = sdir / name
        if p.exists():
            return p
    return sdir / names[0]
