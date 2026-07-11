# Controller/Tools/config_io.py
"""
Thin wrapper around config.load_config() that exposes a typed view
(ValidConfig) for tools that prefer attribute access over digging in the
raw dict.

This intentionally *does not* re-parse YAML/JSON itself. All discovery,
schema migration, defaults, and validation live in Controller/config.py.
If you need a new piece of config, add it there first, then surface it
through this wrapper as needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
import os

from config import load_config, _mgmt_root  # type: ignore[attr-defined]


VEIN_RUNTIME_EXECUTABLE = "Vein/Binaries/Win64/VeinServer-Win64-Test.exe"


@dataclass(frozen=True)
class ValidConfig:
    # Raw config dict as returned by config.load_config()
    raw: Dict[str, Any]

    # Where the config file lives on disk (best-effort guess)
    path: Path

    # Normalized core paths
    server_dir: Path
    runtime_dir: Path
    logs_dir: Path
    save_dir: Path
    absolute_log_file: Optional[Path]

    # Executable selection
    server_executables: List[str]
    preferred_exe: Optional[str]
    selected_exe: Path

    # Monitor / heartbeat knobs
    hb_seconds: int
    fresh_window_multiplier: float

    # Structured sub-configs (pass-through)
    steam: Dict[str, Any]
    backups: Dict[str, Any]
    discord: Dict[str, Any]


def _discover_cfg_path(explicit: str | os.PathLike | None) -> Path:
    """
    Best-effort mirror of config._candidate_configs() logic, but kept simple.
    This is only used for the ValidConfig.path metadata and logging.
    """
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p

    env = os.environ.get("VEIN_CONFIG", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p

    mgmt = _mgmt_root()
    for rel in ("Config/config.yaml", "Config/config.yml", "Config/config.json"):
        p = mgmt / rel
        if p.exists():
            return p

    # Fallback: still return something reasonable even if it doesn't exist yet.
    return _mgmt_root() / "Config" / "config.yaml"


def _as_int(d: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(d.get(key, default))
    except Exception:
        return default


def _as_float(d: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(d.get(key, default))
    except Exception:
        return default


def load_and_validate_config(
    cfg_path: str | os.PathLike | None = None, *, fatal: bool = True
) -> ValidConfig:
    """
    Return a ValidConfig with normalized paths and knobs.

    Any error raised by config.load_config() is propagated by default. If
    fatal=False, those errors are wrapped in a RuntimeError instead so
    callers can decide what to do.
    """
    path = _discover_cfg_path(cfg_path)

    try:
        raw = load_config()
    except Exception as e:  # defensive; config.load_config does real validation
        if fatal:
            raise
        raise RuntimeError(f"Could not load config: {e}") from e

    # Core paths (all should be absolute thanks to config.load_config())
    server_dir = Path(raw.get("server_dir", "")).expanduser()
    runtime_dir = Path(raw.get("runtime_dir", "")).expanduser()
    logs_dir = Path(raw.get("logs_dir", "")).expanduser()
    save_dir = Path(raw.get("save_dir", "")).expanduser()

    abs_log = raw.get("absolute_log_file") or (raw.get("paths") or {}).get(
        "absolute_log_file"
    )
    absolute_log_file = Path(abs_log).expanduser() if abs_log else None

    # Executables
    server_executables = list(raw.get("server_executables") or [])
    preferred_exe = raw.get("preferred_exe") or None
    selected_name: Optional[str] = None

    if preferred_exe and preferred_exe in server_executables:
        selected_name = preferred_exe
    elif server_executables:
        selected_name = server_executables[0]

    runtime_exe = server_dir / VEIN_RUNTIME_EXECUTABLE
    if runtime_exe.is_file():
        # VeinServer.exe is a small Unreal bootstrapper. In the SteamCMD
        # dedicated-server layout it can build a duplicated relative path;
        # launch the adjacent runtime binary directly when it is present.
        selected_exe = runtime_exe
    elif selected_name:
        selected_exe = server_dir / selected_name
    else:
        # Reasonable fallback; config.load_config() already warned if
        # server_executables was empty.
        selected_exe = server_dir / "VeinServer.exe"

    # Monitor / heartbeat knobs
    monitor = raw.get("monitor") or {}
    hb_seconds = _as_int(
        monitor,
        "heartbeat_seconds",
        raw.get("monitor_heartbeat_interval_seconds", 300),
    )
    fresh_window_multiplier = _as_float(monitor, "fresh_window_multiplier", 2.0)

    # Sub-configs
    steam = raw.get("steam") or {}
    backups = raw.get("backups") or {}
    discord = monitor.get("discord") or raw.get("discord") or {}

    return ValidConfig(
        raw=raw,
        path=path,
        server_dir=server_dir,
        runtime_dir=runtime_dir,
        logs_dir=logs_dir,
        save_dir=save_dir,
        absolute_log_file=absolute_log_file,
        server_executables=server_executables,
        preferred_exe=preferred_exe,
        selected_exe=selected_exe,
        hb_seconds=hb_seconds,
        fresh_window_multiplier=fresh_window_multiplier,
        steam=steam,
        backups=backups,
        discord=discord,
    )
