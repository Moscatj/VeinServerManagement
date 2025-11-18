from __future__ import annotations

from pathlib import Path
from typing import List

from config_helper import config, get_path

__all__ = [
    "server_dir",
    "logs_dir",
    "save_dir",
    "absolute_log_file",
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
    return Path(config.get("save_dir") or (sd / "Vein" / "Saved"))


def absolute_log_file() -> str:
    return str(config.get("absolute_log_file", "") or "")


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
