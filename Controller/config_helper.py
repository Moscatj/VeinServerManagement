"""
config_helper.py — ergonomic helpers around the raw config dict.
- Single source of truth for feature gates and structured sub-config (backups).
- Backward compatible migration from legacy keys.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple

from config import load_config

# ---------------------------------------------------------------------------
# Load once and share
# ---------------------------------------------------------------------------
config: Dict[str, Any] = load_config()
features: Dict[str, Any] = config.get("features", {}) or {}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _norm_path(p: str | os.PathLike | None) -> str:
    if not p:
        return ""
    return os.path.normpath(os.path.abspath(str(p)))

def _deep_get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def _deep_set(d: Dict[str, Any], path: str, value) -> None:
    cur = d
    parts = path.split(".")
    for k in parts[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[parts[-1]] = value

# ------- Structured getters (single source of truth) -------
def cfg_version() -> int:
    return int(config.get("version", 1))

def paths_cfg() -> dict:
    p = (config.get("paths") or {}).copy()
    # normalize
    for k in list(p.keys()):
        v = p[k]
        if isinstance(v, str):
            p[k] = _norm_path(v)
    return p

def logs_dir() -> str:
    return paths_cfg().get("logs", "")

def saves_dir() -> str:
    return paths_cfg().get("saves", "")

# Backups (save files)
def backups_cfg_v2() -> dict:
    b = (config.get("backup") or {}).copy()
    # normalize root
    root = b.get("root") or (paths_cfg().get("backup_root"))
    b["root"] = _norm_path(root) if root else ""
    # normalize nested logs policy too (just passthrough here)
    return b

def backup_root() -> str:
    return backups_cfg_v2().get("root", "")

# Log snapshots (new)
def log_snap_cfg() -> dict:
    b = backups_cfg_v2()
    logs = (b.get("logs") or {}).copy()
    # defaults
    logs.setdefault("enabled", True)
    logs.setdefault("root", _norm_path((b.get("root") or "") + "\\Logs") if b.get("root") else "")
    logs.setdefault("max_files", 100)
    logs.setdefault("max_age_days", 30)
    logs.setdefault("include_tail_in_saves", False)
    logs.setdefault("tail_kb", 256)
    # normalize root
    if isinstance(logs.get("root"), str):
        logs["root"] = _norm_path(logs["root"])
    return logs

# ---------------------------------------------------------------------------
# Migration (in-memory; does not rewrite YAML)
# - Prefer backups.enable over features.enable_backups
# - Carry legacy backup_* keys into backups.* view for unified access
# ---------------------------------------------------------------------------
def _migrate_backups_view() -> None:
    b = config.get("backups")
    if not isinstance(b, dict):
        b = {}
        config["backups"] = b

    # 1) enable: prefer backups.enable; otherwise adopt legacy features.enable_backups
    if "enable" not in b:
        legacy = bool(features.get("enable_backups", True))
        b["enable"] = legacy

    # 2) root & folders: prefer backups.root/folders; else legacy keys
    if "root" not in b:
        root = config.get("backup_root")
        if root:
            b["root"] = root
    if "folders" not in b:
        folders = config.get("backup_folders")
        if isinstance(folders, dict):
            b["folders"] = folders

    # 3) save_filenames (optional locality)
    if "save_filenames" not in b:
        names = config.get("save_filenames")
        if isinstance(names, list):
            b["save_filenames"] = names

    if "save_dir" not in b:
        sdir = config.get("save_dir") or (config.get("paths", {}) or {}).get("save_dir")
        if sdir:
            b["save_dir"] = sdir

    # 4) retention: build a default from legacy globals; map nightly overrides if present
    ret = b.get("retention")
    if not isinstance(ret, dict):
        ret = {}
        b["retention"] = ret

    default_max = int(config.get("max_backups", 10))
    default_age = int(config.get("backup_max_age_days", 7))
    ret.setdefault("default", {"max_backups": default_max, "max_age_days": default_age})

    nightly = config.get("nightly_backup", {}) or {}
    if nightly:
        ret.setdefault("Nightly", {
            "max_backups": int(nightly.get("max_backups", default_max)),
            "max_age_days": int(nightly.get("max_backup_age_days", max(default_age, 30))),
        })

_migrate_backups_view()

# ---------------------------------------------------------------------------
# Feature gates (existing)
# ---------------------------------------------------------------------------
def is_feature_enabled(feature_key: str, default: bool = True) -> bool:
    return bool(features.get(feature_key, default))

def is_discord_channel_enabled(channel: str) -> bool:
    if not bool(features.get("enable_discord", True)):
        return False
    key = f"discord_{(channel or '').strip().lower()}"
    return bool(features.get(key, True))

# ---------------------------------------------------------------------------
# Typed getters (existing)
# ---------------------------------------------------------------------------
def get_bool(key: str, default: bool = False) -> bool:
    return bool(config.get(key, default))

def get_int(key: str, default: int = 0) -> int:
    val = config.get(key, default)
    try:
        return int(val)
    except Exception:
        return int(default)

def get_list(key: str, default: Optional[List[Any]] = None) -> List[Any]:
    val = config.get(key)
    if isinstance(val, list):
        return val
    return list(default or [])

def get_dict(key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    val = config.get(key)
    if isinstance(val, dict):
        return val
    return dict(default or {})

# ---------------------------------------------------------------------------
# Path helper (existing)
# ---------------------------------------------------------------------------
def get_path(key: str) -> str:
    val = config.get(key, "")
    if not isinstance(val, str):
        return ""
    return _norm_path(val)

# ---------------------------------------------------------------------------
# Backups — canonical helpers
# ---------------------------------------------------------------------------
def backups_cfg() -> Dict[str, Any]:
    """
    Unified backups view with legacy fallbacks already merged by _migrate_backups_view().
    """
    b = config.get("backups", {}) or {}
    # normalize paths for easy consumption
    root = _norm_path(b.get("root"))
    folders = b.get("folders") or {}
    norm_folders = {}
    for k, v in folders.items():
        norm_folders[k] = _norm_path(v) if isinstance(v, str) else v
    out = dict(b)
    out["root"] = root
    out["folders"] = norm_folders
    # ensure retention block exists
    if b.get("save_dir"):
        out["save_dir"] = _norm_path(b["save_dir"])
    if "retention" not in out or not isinstance(out["retention"], dict):
        out["retention"] = {"default": {"max_backups": 10, "max_age_days": 7}}
    return out

def backups_enabled(default: bool = True) -> bool:
    """
    Single, definitive toggle. Prefer backups.enable; no longer reads features.enable_backups
    except as already migrated in _migrate_backups_view().
    """
    b = backups_cfg()
    return bool(b.get("enable", default))

def backup_folders() -> Dict[str, str]:
    return backups_cfg().get("folders", {}) or {}

def backup_retention_for(reason: str) -> Dict[str, int]:
    """
    Returns {'max_backups': int, 'max_age_days': int} for a reason (e.g., Nightly/Crash/AutoSave),
    falling back to 'default' or sane defaults.
    """
    b = backups_cfg()
    ret = b.get("retention", {}) or {}
    r = ret.get(reason) or ret.get("default") or {"max_backups": 10, "max_age_days": 7}
    return {"max_backups": int(r.get("max_backups", 10)), "max_age_days": int(r.get("max_age_days", 7))}
