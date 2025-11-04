"""
config_helper.py — ergonomic helpers around the raw config dict.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from config import load_config

# Load once and share
config: Dict[str, Any] = load_config()
features: Dict[str, Any] = config.get("features", {})

# ---------- Feature gates ----------
def is_feature_enabled(feature_key: str, default: bool = True) -> bool:
    return bool(features.get(feature_key, default))

def is_discord_channel_enabled(channel: str) -> bool:
    if not bool(features.get("enable_discord", True)):
        return False
    key = f"discord_{(channel or '').strip().lower()}"
    return bool(features.get(key, True))

# ---------- Typed getters ----------
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

# ---------- Path helper ----------
def get_path(key: str) -> str:
    val = config.get(key, "")
    if not isinstance(val, str):
        return ""
    return os.path.normpath(os.path.abspath(val))
