from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from config_helper import config, get_path, backups_cfg
from Tools.process import resolve_server_executable
from Tools import paths

__all__ = ["resolve_save_file", "summarize_config"]


def resolve_save_file() -> Path:
    return paths.resolve_save_file()


def summarize_config() -> Dict[str, object]:
    server_dir = paths.server_dir()
    logs_dir = paths.logs_dir()
    save_dir = paths.save_dir()
    exe = resolve_server_executable(
        server_dir, list(config.get("server_executables", []))
    )
    bview = backups_cfg()
    headless = bool(config.get("headless_mode", False))
    return {
        "server_dir": str(server_dir),
        "backup_root": str(bview.get("root") or get_path("backup_root")),
        "save_dir": str(save_dir),
        "logs_dir": str(logs_dir),
        "executable_selected": str(exe) if exe else None,
        "executable_candidates": list(config.get("server_executables", [])),
        "map_url": config.get("map_path", "/Game/Vein/Maps/ChamplainValley?listen"),
        "max_players": int(config.get("max_players", 8)),
        "game_port": int(config.get("game_port", 7777)),
        "query_port": int(config.get("query_port", 27015)),
        "multi_home_ip": str(config.get("multi_home_ip", "0.0.0.0")),
        "steamcmd_path": str(config.get("steamcmd_path", "") or ""),
        "monitor_log_wait_timeout_seconds": int(
            config.get("monitor_log_wait_timeout_seconds", 60)
        ),
        "headless": headless,
        "app_id": str(config.get("app_id", "") or "") or None,
        "features": {
            "enable_discord": bool(
                config.get("features", {}).get("enable_discord", True)
            ),
            "enable_backups (legacy)": bool(
                config.get("features", {}).get("enable_backups", True)
            ),
            "enable_steam_update": bool(
                config.get("features", {}).get("enable_steam_update", True)
            ),
            "enable_crash_monitor": bool(
                config.get("features", {}).get("enable_crash_monitor", True)
            ),
            "enable_query_port": bool(config.get("enable_query_port", True)),
        },
        "backups": {
            "enable": bool(bview.get("enable", True)),
            "root": bview.get("root"),
            "folders": bview.get("folders"),
            "retention": bview.get("retention"),
        },
    }
