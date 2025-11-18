from __future__ import annotations

"""
Helpers for runtime coordination files (flags, locks, PID markers).

This module centralizes the shared paths under Runtime/ and the helpers
that read/write those markers so controllers and monitors can import a
single focused API instead of reaching into utils.py.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from config_helper import config, get_path
from Tools.state_io import (
    default_state as _default_server_state,
    write_state as _write_server_state,
)


__all__ = [
    "PROJECT_ROOT",
    "CONTROLLER_DIR",
    "RUNTIME_DIR",
    "STARTUP_LOCK",
    "QUIET_UNTIL",
    "RESTARTING_LOCK",
    "RESTART_STAMP",
    "STATE_FLAG",
    "PID_SERVER",
    "SERVER_STATE",
    "SHUTDOWN_FLAG",
    "write_flag",
    "read_flag",
    "clear_flag",
    "begin_intentional_shutdown",
    "end_intentional_shutdown",
    "is_shutdown_in_progress",
    "set_server_state",
    "clear_pid_file",
    "clear_runtime_markers",
    "create_startup_lock",
    "clear_startup_lock",
    "startup_grace_active",
    "set_autorestart_quiet_period",
    "autorestart_quiet_active",
]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER_DIR = PROJECT_ROOT / "Controller"


def _resolve_runtime_dir() -> Path:
    path = get_path("runtime_dir")
    if path:
        return Path(path)
    return PROJECT_ROOT / "Runtime"


RUNTIME_DIR: Path = _resolve_runtime_dir()
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

STARTUP_LOCK = RUNTIME_DIR / "startup_in_progress.lock"
QUIET_UNTIL = RUNTIME_DIR / "no_autorestart.until"
RESTARTING_LOCK = RUNTIME_DIR / "restarting.lock"
RESTART_STAMP = RUNTIME_DIR / "last_restart_at.txt"

STATE_FLAG = RUNTIME_DIR / "server_running.flag"
PID_SERVER = RUNTIME_DIR / "server.pid"
SERVER_STATE = RUNTIME_DIR / "server_state.json"
SHUTDOWN_FLAG = RUNTIME_DIR / "shutdown_in_progress.flag"


def _now() -> float:
    return time.time()


def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def write_flag(pid: int, exe: str, map_url: str) -> None:
    data = {
        "pid": pid,
        "exe": exe,
        "map": map_url,
        "started_at": datetime.utcnow().isoformat(),
    }
    try:
        STATE_FLAG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Flag] Failed to write flag: {e}")


def read_flag() -> Dict[str, Any] | None:
    if not STATE_FLAG.exists():
        return None
    try:
        return json.loads(STATE_FLAG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Flag] Failed to read flag: {e}")
        return None


def clear_flag() -> None:
    try:
        STATE_FLAG.unlink(missing_ok=True)
    except Exception as e:
        print(f"[Flag] Failed to clear flag: {e}")


def begin_intentional_shutdown(window_sec: int = 180) -> None:
    """Mark an intentional shutdown and open a quiet window to suppress restarts."""
    try:
        SHUTDOWN_FLAG.write_text(str(int(_now())), encoding="utf-8")
    except Exception:
        pass
    set_autorestart_quiet_period(max(0, window_sec))


def end_intentional_shutdown() -> None:
    """Clear the intentional shutdown marker."""
    try:
        SHUTDOWN_FLAG.unlink(missing_ok=True)
    except Exception:
        pass


def is_shutdown_in_progress(max_age_seconds: int = 900) -> bool:
    """True if shutdown flag exists and is fresh (default ≈15 min)."""
    try:
        if not SHUTDOWN_FLAG.exists():
            return False
        age = _now() - SHUTDOWN_FLAG.stat().st_mtime
        return age <= max_age_seconds
    except Exception:
        return False


def set_server_state(process_running: bool, pid: int = 0, **extra) -> None:
    """
    Unified writer for Runtime/server_state.json.

    Uses Tools.state_io so server_state.json has:
      - schema/version
      - status ("running"/"stopped")
      - pid
      - last_updated (UTC ISO)
      - optional extra fields (last_start_utc, exe, cwd, last_exit_code, etc.)

    If anything goes wrong, we fall back to the legacy minimal format so we
    never completely lose state. Extras are sanitized to avoid json issues.
    """

    status = "running" if process_running else "stopped"

    safe_extra: Dict[str, Any] = {}
    for k, v in extra.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            safe_extra[k] = v
        else:
            safe_extra[k] = str(v)

    try:
        state = _default_server_state(
            status=status,
            pid=int(pid),
            headless=bool(config.get("headless_mode", False)),
            version="runtime.set_server_state",
        )
        if safe_extra:
            state.update(safe_extra)
        _write_server_state(SERVER_STATE, state)
    except Exception:
        try:
            data = {
                "process_running": bool(process_running),
                "pid": int(pid),
                **safe_extra,
            }
            _atomic_write_json(SERVER_STATE, data)
        except Exception:
            pass


def clear_pid_file() -> None:
    try:
        PID_SERVER.unlink(missing_ok=True)
    except Exception:
        pass


def clear_runtime_markers() -> None:
    """Remove all runtime hints about an active server session."""
    clear_flag()
    clear_pid_file()
    try:
        SERVER_STATE.unlink(missing_ok=True)
    except Exception:
        pass


def create_startup_lock() -> None:
    try:
        STARTUP_LOCK.write_text(str(int(_now())), encoding="utf-8")
    except Exception:
        pass


def clear_startup_lock() -> None:
    try:
        STARTUP_LOCK.unlink(missing_ok=True)
    except Exception:
        pass


def startup_grace_active(max_age_seconds: int = 180) -> bool:
    """True if 'startup_in_progress.lock' is fresh (prevents false crash handling mid-boot)."""
    try:
        if not STARTUP_LOCK.exists():
            return False
        age = _now() - STARTUP_LOCK.stat().st_mtime
        return age <= max_age_seconds
    except Exception:
        return False


def set_autorestart_quiet_period(seconds: int = 120) -> None:
    """During this window, monitors should not trigger restarts."""
    try:
        QUIET_UNTIL.write_text(str(int(_now() + max(0, seconds))), encoding="utf-8")
    except Exception:
        pass


def autorestart_quiet_active() -> bool:
    try:
        if not QUIET_UNTIL.exists():
            return False
        until = int(QUIET_UNTIL.read_text(encoding="utf-8").strip() or "0")
        return _now() < until
    except Exception:
        return False
