# Controller/Tools/config_io.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from glob import glob
from typing import List, Optional
import json, sys, shutil, os, time

@dataclass(frozen=True)
class ValidConfig:
    # raw
    raw: dict
    path: Path

    # normalized paths
    server_dir: Path
    runtime_dir: Path
    logs_dir: Path
    save_dir: Path

    # log file resolution
    absolute_log_file: Optional[Path]

    # executables
    server_executables: List[str]
    preferred_exe: Optional[str]
    selected_exe: Path  # resolved full path (must exist)

    # monitors
    hb_seconds: int
    fresh_window_multiplier: float

    # optional groups
    steam: dict
    backups: dict
    discord: dict

def _fatal(msg: str) -> "NoReturn":  # type: ignore
    print(f"[FATAL] {msg}")
    sys.exit(1)

def _warn(msg: str) -> None:
    print(f"[WARN]  {msg}")

def _info(msg: str) -> None:
    print(f"[info]  {msg}")

def _as_path(v) -> Path:
    return Path(str(v)).expanduser()

def _choose_exe(server_dir: Path, exes: List[str], preferred: Optional[str]) -> Path:
    if not exes:
        _fatal("server_executables is empty in config.json")
    # prefer explicit preferred_exe if set
    if preferred:
        pe = server_dir / preferred
        return pe
    # otherwise: prefer any that contains '-Test', else first
    for name in exes:
        if "-Test" in name:
            return server_dir / name
    return server_dir / exes[0]

def _bound(v, lo, hi, cast):
    try:
        x = cast(v)
    except Exception:
        return lo
    if x < lo: return lo
    if x > hi: return hi
    return x

def load_and_validate_config(cfg_path: str | Path) -> ValidConfig:
    p = Path(cfg_path)
    if not p.exists():
        _fatal(f"Config file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _fatal(f"Could not parse config JSON: {e}")

    # --- Required path-ish keys
    for req in ("server_dir", "runtime_dir", "logs_dir", "save_dir"):
        if req not in raw:
            _fatal(f"Missing '{req}' in config.json")

    server_dir = _as_path(raw["server_dir"])
    runtime_dir = _as_path(raw["runtime_dir"])
    logs_dir   = _as_path(raw["logs_dir"])
    save_dir   = _as_path(raw["save_dir"])

    # --- Resolve absolute_log_file if provided
    abs_log = (raw.get("absolute_log_file") or "").strip()
    absolute_log_file = _as_path(abs_log) if abs_log else None

    # --- Executable selection
    exes = list(raw.get("server_executables", []))
    preferred = (raw.get("preferred_exe") or "").strip() or None
    selected = _choose_exe(server_dir, exes, preferred)

    # --- Heartbeat knobs
    mon = raw.get("monitor", {}) or {}
    hb_seconds = _bound(mon.get("heartbeat_seconds", 60), 5, 3600, int)
    fresh_mult = _bound(mon.get("fresh_window_multiplier", 2.0), 0.25, 10.0, float)

    # --- Optional groups pass-through
    steam   = raw.get("steam", {}) or {}
    backups = raw.get("backups", {}) or {}
    discord = (mon.get("discord", {}) if isinstance(mon.get("discord", {}), dict) else {}) or {}

    # --- Exist checks (warn vs fatal)
    if not server_dir.exists():
        _warn(f"server_dir does not exist: {server_dir}")
    if not logs_dir.exists():
        _warn(f"logs_dir does not exist: {logs_dir}")
    if not save_dir.exists():
        _warn(f"save_dir does not exist: {save_dir}")

    # runtime dir is our responsibility
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _fatal(f"Could not create runtime_dir '{runtime_dir}': {e}")

    # Resolve and verify selected exe
    if not selected.exists():
        # Allow SteamCMD workflow to install later, but warn loudly
        _warn(f"Selected server executable not found yet: {selected}")
        # If an alternative exists, hint
        found = []
        for name in exes:
            cand = server_dir / name
            if cand.exists():
                found.append(str(cand))
        if found:
            _info("Other executables present:\n  - " + "\n  - ".join(found))

    # Optional: verify SteamCMD if path provided
    steamcmd = steam.get("steamcmd_path")
    if steamcmd:
        sc = _as_path(steamcmd)
        if not sc.exists():
            _warn(f"steam.steamcmd_path does not exist: {sc}")

    # Optional: ensure Logs/Backups folders exist if configured as absolute
    if absolute_log_file:
        try:
            absolute_log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _warn(f"Could not ensure absolute_log_file dir: {absolute_log_file.parent} ({e})")

    return ValidConfig(
        raw=raw, path=p,
        server_dir=server_dir, runtime_dir=runtime_dir, logs_dir=logs_dir, save_dir=save_dir,
        absolute_log_file=absolute_log_file,
        server_executables=exes, preferred_exe=preferred, selected_exe=selected,
        hb_seconds=hb_seconds, fresh_window_multiplier=fresh_mult,
        steam=steam, backups=backups, discord=discord
    )
