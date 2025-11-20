"""monitor_log.py — Vein log tailer

- Tails the active Vein log file (auto-pick or config.absolute_log_file)
- Detects ready state, player auth/join/character/disconnect, autosave, crashes
- Posts Discord notifications via utils.send_discord_message() respecting feature flags
- Writes a small PID file so GUI can see it's alive: <runtime>/log_monitor.pid
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict, Deque, List
from glob import glob
from collections import deque

from Tools import backups as _bk
from Tools import mgmt_logs

from config_helper import config
from Tools.paths import logs_dir, absolute_log_file
from Tools.process import is_server_running, current_headless_flag
from Tools.discord import send_discord_message, is_discord_channel_enabled
from Tools.discord import send_discord_message
from Tools.backups_api import make_backup as backup_save_file
from Tools.runtime import RUNTIME_DIR, SHUTDOWN_FLAG
from Tools.vein_http_api import (
    get_configured_client,
    VeinHTTPAPIError,
    VeinHTTPClient,
)

LOGS_DIR = logs_dir()
ABSOLUTE_LOG_FILE = absolute_log_file()
PID_FILE = RUNTIME_DIR / "log_monitor.pid"
ROOT_DIR = Path(__file__).resolve().parent.parent
HTTP_LOG_FILE = mgmt_logs.subsystem_dir("http_api") / "http_api.log"
PLAYER_SNAPSHOT_FILE = RUNTIME_DIR / "player_characters.json"

# ---- Config knobs (with sensible defaults) ----
_MON = dict(config.get("log_monitor") or config.get("monitor") or {})
TRACK = dict(_MON.get("track", {}))
BACKUPS = dict(_MON.get("backups", {}))
NOTIFY = dict(_MON.get("notify", {}))
STATE_REFRESH_S = int(_MON.get("state_refresh_seconds", 15))
LINGER_WHEN_SERVER_DOWN = bool(_MON.get("linger_when_server_down", True))
RECHECK_NEWEST_EVERY_S = int(_MON.get("recheck_newest_every_seconds", 5))

HEARTBEAT_INTERVAL_S = int(
    _MON.get(
        "heartbeat_interval_seconds",
        config.get("monitor_heartbeat_interval_seconds", 300),
    )
)
WAIT_FOR_LOG_S = int(_MON.get("wait_for_log_appearance_seconds", 120))
TAIL_POLL_MS = int(_MON.get("tail_poll_interval_ms", 500))

TRACK_STARTUP = bool(TRACK.get("startup", True))
TRACK_AUTH = bool(TRACK.get("auth", True))
TRACK_JOIN = bool(TRACK.get("join", True))
TRACK_CHARACTER = bool(TRACK.get("character", True))
TRACK_DISCONNECT = bool(TRACK.get("disconnect", True))
TRACK_AUTOSAVE = bool(TRACK.get("autosave", True))
TRACK_CRASH = bool(TRACK.get("crash", True))
TRACK_HEARTBEAT = bool(TRACK.get("heartbeat", True))
TRACK_HTTP_API = bool(TRACK.get("http_api", True))

NOTIFY_STARTUP = bool(NOTIFY.get("startup", True))
NOTIFY_JOINABLE = bool(NOTIFY.get("joinable", True))
NOTIFY_AUTH = bool(NOTIFY.get("auth", True))
NOTIFY_JOIN = bool(NOTIFY.get("join", True))
NOTIFY_CHARACTER = bool(NOTIFY.get("character", True))
NOTIFY_DISC = bool(NOTIFY.get("disconnect", True))
NOTIFY_AUTOSAVE = bool(NOTIFY.get("autosave", False))
NOTIFY_CRASH = bool(NOTIFY.get("crash", True))
NOTIFY_HB = bool(NOTIFY.get("heartbeat", False))
NOTIFY_STATUS = bool(NOTIFY.get("monitor_status", True))

# ---- Regex library tuned to real Vein.log lines ----
RX_LISTEN = re.compile(r"RamjetSteamNetDriver_.*started listening on (\d+)", re.I)
RX_WORLD_UP = re.compile(r"LogWorld: Bringing World .* up for play", re.I)
RX_STEAM_OK = re.compile(r"Steamworks server initialized", re.I)

RX_LOGIN = re.compile(r"LogNet: Login request:")
RX_AUTH_OK = re.compile(r"LogRamjetNetworking: Authenticated (\d+)")
RX_JOINED = re.compile(r"LogNet: Join succeeded:\s*(.+)")
RX_CHARSEL = re.compile(r"selected character .* \(aka ([^)]+)\)", re.I)
RX_CHARSEL_FULL = re.compile(
    r"Player\s+(?P<name>.+?)\s+selected character\s+(?P<char>[A-F0-9]+)",
    re.I,
)
RX_LOGIN_NAME_ID = re.compile(r"\?Name=([^?]+)\?\?ID=(\d+)", re.I)
RX_SOCKET_STEAMID = re.compile(r"steamid:(\d+)", re.I)
RX_AUTH_SESSION_END = re.compile(r"Ended auth session for ID\s+(\d+)", re.I)
RX_PLAYER_AUTH_OK = re.compile(
    r"LogVein:\s+Player\s+(?P<steam>\d+).+authenticated successfully",
    re.I,
)
RX_PLAYER_STATE_ID = re.compile(r"LogVein:\s+PlayerState ID changed to\s+(\d+)", re.I)
RX_DISC = re.compile(r"closed by peer|Logout|Connection closed", re.I)

RX_AUTOSAVE = re.compile(r"LogVeinSaveGame: Saved save game to disk", re.I)

RX_CRASH = re.compile(
    r"Fatal error|Access violation|EXCEPTION_ACCESS_VIOLATION|Assertion failed|ensure\(!\)",
    re.I,
)

_BEH = dict((_MON.get("heartbeat", {}) or {}))

_MONITOR_HB_CHANNEL = str(_BEH.get("channel", "monitor"))
_MONITOR_HB_PREFIX = str(_BEH.get("prefix", "🩺"))

# Backups events section
_BACKUP_CFG = dict(config.get("backups", {}) or {})
_BACKUP_EVENTS = dict(_BACKUP_CFG.get("events", {}) or {})
_BACKUP_TRIGGERS = dict(_BACKUP_CFG.get("triggers", {}) or {})

_PLAYER_CACHE: Dict[str, Dict[str, Any]] = {}
_NAME_TO_ID: Dict[str, str] = {}
_ID_TO_NAME: Dict[str, str] = {}
_PLAYER_EVENT_LIMIT = 32
_PLAYER_CACHE_LIMIT = 12
_PLAYER_SNAPSHOT_DIRTY = False
_LAST_PLAYER_SNAPSHOT_WRITE = 0.0
_PLAYER_SNAPSHOT_INTERVAL = 2.0
_HTTP_STATE: Optional[Dict[str, Any]] = None
_HTTP_DISABLED_LOGGED = False


def _trigger_section(new_key: str, legacy_key: str) -> dict:
    """Merge backups.triggers + backups.events for compatibility."""
    merged: dict[str, Any] = {}
    legacy = _BACKUP_EVENTS.get(legacy_key)
    if isinstance(legacy, dict):
        merged.update(legacy)
    trig = _BACKUP_TRIGGERS.get(new_key)
    trig_dict: dict[str, Any] = {}
    if isinstance(trig, bool):
        trig_dict = {"enabled": trig}
    elif isinstance(trig, dict):
        trig_dict = trig
    merged.update(trig_dict)
    if "enabled" not in merged and "save_backup" in trig_dict:
        merged["enabled"] = bool(trig_dict.get("save_backup"))
    return merged


_EVT_AUTOSAVE = _trigger_section("on_autosave", "autosave")
_EVT_LAST = _trigger_section("last_player", "last_player")
_EVT_CRASH = _trigger_section("on_crash_detect", "crash")
_EVT_SHUT = _trigger_section("shutdown", "shutdown")

AUTOSAVE_ENABLED = bool(_EVT_AUTOSAVE.get("enabled", True))
AUTOSAVE_COOLDOWN = int(
    _EVT_AUTOSAVE.get(
        "cooldown_seconds",
        int(config.get("autosave_backup_cooldown_seconds", 300)),
    )
)

LAST_ENABLED = bool(_EVT_LAST.get("enabled", True))
LAST_COOLDOWN = int(_EVT_LAST.get("cooldown_seconds", 600))

CRASH_ENABLED = bool(_EVT_CRASH.get("enabled", True))
CRASH_DEBOUNCE = int(_EVT_CRASH.get("debounce_seconds", 120))

SHUT_ENABLED = bool(_EVT_SHUT.get("enabled", True))
SHUT_GRACE = int(_EVT_SHUT.get("grace_seconds", 900))

# shutdown flag (we re-create the same path utils uses)
# Provided by Tools.runtime; kept for backward compat with local constants
# SHUTDOWN_FLAG = RUNTIME_DIR / "shutdown_in_progress.flag"


def _backup(reason: str) -> None:
    """Fire a backup with the canonical Tools/backups engine."""
    try:
        _bk.make_backup(reason=reason, files=None, dst=None)
    except Exception:
        # silent on monitor; Tools/backups already prints and Discords meaningful errors
        pass


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve().samefile(b.resolve())
    except Exception:
        return str(a) == str(b)


def _resolve_active_log() -> Path | None:
    """
    Pick the best current Vein log file to tail.
    Priority:
      1) config["absolute_log_file"] if set and exists
      2) <logs_dir>/Vein.log if exists
      3) Most-recent *.log under common UE folders:
         - <server_dir>/Vein/Saved/Logs
         - <server_dir>/Saved/Logs
         - <logs_dir>/*.log
    Returns Path or None if nothing found yet.
    """
    # 1) Absolute override (from config)
    abs_log = (config.get("absolute_log_file") or "").strip()
    if abs_log:
        p = Path(abs_log)
        if p.exists():
            return p

    # 2) Logs dir + Vein.log
    logs_dir = Path(config.get("logs_dir") or "").expanduser()
    if logs_dir:
        p = logs_dir / "Vein.log"
        if p.exists():
            return p

    # 3) Common Unreal log locations
    server_dir = Path(config.get("server_dir") or "").expanduser()
    candidates: list[str] = []

    # e.g. G:/Servers/VeinServer/Vein/Saved/Logs/*.log
    if server_dir:
        candidates += glob(str(server_dir / "Vein" / "Saved" / "Logs" / "*.log"))
        candidates += glob(str(server_dir / "Saved" / "Logs" / "*.log"))

    # Fallback: any .log inside configured logs_dir
    if logs_dir:
        candidates += glob(str(logs_dir / "*.log"))

    # Pick newest by mtime
    newest: tuple[float, Path] | None = None
    for s in candidates:
        try:
            p = Path(s)
            mt = p.stat().st_mtime
            if (newest is None) or (mt > newest[0]):
                newest = (mt, p)
        except FileNotFoundError:
            continue

    if newest is None:
        return None
    return newest[1]


def _runtime_paths() -> dict:
    """
    Returns the paths this monitor uses inside Runtime/.
    Keys match what the GUI StatusPoller expects: 'state_log' and 'pid_log'.
    """
    # Use the same runtime dir as utils
    base = RUNTIME_DIR
    # Ensure the directory exists (already done in utils, but cheap)
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    return {
        "runtime": base,
        "state_log": base / "log_monitor.state.json",  # GUI reads this
        "pid_log": base / "log_monitor.pid",  # GUI checks this
        "stop_log": base / "log_monitor.stop",  # touch this to stop monitor
    }


def _discord(msg: str, channel: str = "monitor"):
    if is_discord_channel_enabled(channel):
        send_discord_message(msg, channel=channel)


def _log_http_api(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    try:
        HTTP_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with HTTP_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    cleaned = " ".join(str(name).split()).strip()
    return cleaned.lower() if cleaned else None


def _name_key(name: Optional[str]) -> Optional[str]:
    norm = _normalize_name(name)
    if not norm:
        return None
    return f"name:{norm}"


def _remember_identity(steam_id: Optional[str], name: Optional[str]) -> None:
    sid = str(steam_id or "").strip()
    if not sid:
        return
    if name:
        norm = _normalize_name(name)
        if norm:
            _NAME_TO_ID[norm] = sid
            _ID_TO_NAME[sid] = name.strip()
            temp_key = _name_key(name)
            if temp_key and temp_key in _PLAYER_CACHE and sid not in _PLAYER_CACHE:
                entry = _PLAYER_CACHE.pop(temp_key)
                entry["steam_id"] = sid
                _PLAYER_CACHE[sid] = entry


def _lookup_id_for_name(name: Optional[str]) -> Optional[str]:
    norm = _normalize_name(name)
    if not norm:
        return None
    return _NAME_TO_ID.get(norm)


def _ensure_player_entry(
    steam_id: Optional[str], name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    key = str(steam_id or "").strip()
    if not key:
        resolved = _lookup_id_for_name(name)
        if resolved:
            key = resolved
        else:
            nk = _name_key(name)
            if nk:
                key = nk
            else:
                return None

    if key not in _PLAYER_CACHE:
        now = _utc_now_iso()
        _PLAYER_CACHE[key] = {
            "steam_id": key if key.isdigit() else "",
            "name": (name or "").strip(),
            "first_seen": now,
            "last_seen": now,
            "online": False,
            "online_state": "offline",
            "in_character_select": False,
            "verified_by_api": False,
            "events": deque(maxlen=_PLAYER_EVENT_LIMIT),
        }
    entry = _PLAYER_CACHE[key]
    if steam_id and not key.isdigit():
        entry = _PLAYER_CACHE.pop(key)
        _PLAYER_CACHE[steam_id] = entry
        entry["steam_id"] = steam_id
        key = steam_id

    if name:
        entry["name"] = name.strip()
        _remember_identity(entry.get("steam_id") or key, name)
    if not entry.get("steam_id"):
        entry["steam_id"] = key if key.isdigit() else ""
    return entry


def _set_player_state(entry: Dict[str, Any], state: str, ts: str) -> None:
    state = state or ""
    if state == "offline":
        entry["online"] = False
        entry["online_state"] = "offline"
        entry["in_character_select"] = False
        entry["last_disconnect"] = ts
    elif state == "select":
        entry["online"] = True
        entry["online_state"] = "select"
        entry["in_character_select"] = True
    elif state == "connecting":
        entry["online"] = True
        entry["online_state"] = "connecting"
        entry["in_character_select"] = False
    elif state == "online":
        entry["online"] = True
        entry["online_state"] = "online"
        entry["in_character_select"] = False
    entry["last_seen"] = ts


def _mark_player_snapshot_dirty() -> None:
    global _PLAYER_SNAPSHOT_DIRTY
    _PLAYER_SNAPSHOT_DIRTY = True


def _prune_player_cache() -> None:
    if len(_PLAYER_CACHE) <= _PLAYER_CACHE_LIMIT * 2:
        return
    ordered = sorted(
        _PLAYER_CACHE.items(),
        key=lambda pair: pair[1].get("last_seen") or "",
        reverse=True,
    )
    keep = {k for k, _ in ordered[:_PLAYER_CACHE_LIMIT]}
    for key in list(_PLAYER_CACHE.keys()):
        if key not in keep:
            _PLAYER_CACHE.pop(key, None)


def _record_player_event(
    steam_id: Optional[str],
    event_type: str,
    *,
    source: str,
    name: Optional[str] = None,
    detail: Optional[str] = None,
    raw_line: Optional[str] = None,
    character_id: Optional[str] = None,
    state: Optional[str] = None,
) -> None:
    entry = _ensure_player_entry(steam_id, name)
    if not entry:
        return

    ts = _utc_now_iso()
    event = {
        "type": event_type,
        "ts": ts,
        "source": source,
    }
    if detail:
        event["detail"] = detail
    if raw_line:
        event["line"] = raw_line
    if character_id:
        event["character_id"] = character_id

    events: Deque[Dict[str, Any]] = entry.setdefault(
        "events", deque(maxlen=_PLAYER_EVENT_LIMIT)
    )
    events.append(event)
    entry["last_seen"] = ts
    if source == "log":
        entry["last_log_event"] = ts
    elif source == "http":
        entry["last_http_event"] = ts

    if character_id:
        entry["current_character_id"] = character_id

    if state:
        _set_player_state(entry, state, ts)

    _mark_player_snapshot_dirty()


def _sorted_player_entries() -> List[Dict[str, Any]]:
    ordered = sorted(
        _PLAYER_CACHE.values(),
        key=lambda entry: entry.get("last_seen") or "",
        reverse=True,
    )
    return ordered[: _PLAYER_CACHE_LIMIT]


def _player_snapshot_from_cache(errors: Optional[List[str]] = None) -> Dict[str, Any]:
    players_out = []
    for entry in _sorted_player_entries():
        payload = {
            "steam_id": entry.get("steam_id") or "",
            "name": entry.get("name") or entry.get("steam_id") or "Unknown",
            "status": entry.get("status"),
            "online": entry.get("online_state") != "offline",
            "in_character_select": bool(entry.get("in_character_select")),
            "online_state": entry.get("online_state")
            or ("online" if entry.get("online") else "offline"),
            "verified_by_api": bool(entry.get("verified_by_api")),
            "current_character_id": entry.get("current_character_id"),
            "last_seen": entry.get("last_seen"),
            "first_seen": entry.get("first_seen"),
            "last_log_event": entry.get("last_log_event"),
            "last_http_event": entry.get("last_http_event"),
            "last_disconnect": entry.get("last_disconnect"),
            "events": list(entry.get("events") or []),
            "player": entry.get("player"),
            "characters": entry.get("characters"),
            "time_connected": entry.get("time_connected"),
            "http": entry.get("http"),
        }
        players_out.append(payload)
    admins = [
        {"steam_id": p.get("steam_id"), "name": p.get("name")}
        for p in players_out
        if (p.get("status") or "").lower() == "admin"
    ]
    return {
        "schema_version": 2,
        "last_updated": _utc_now_iso(),
        "players": players_out,
        "admins": admins,
        "errors": errors or [],
    }


def _flush_player_snapshot_if_needed(
    *, force: bool = False, errors: Optional[List[str]] = None
) -> None:
    global _PLAYER_SNAPSHOT_DIRTY, _LAST_PLAYER_SNAPSHOT_WRITE
    if not force and not _PLAYER_SNAPSHOT_DIRTY:
        return
    now = time.time()
    if not force and (now - _LAST_PLAYER_SNAPSHOT_WRITE) < _PLAYER_SNAPSHOT_INTERVAL:
        return
    payload = _player_snapshot_from_cache(errors)
    _write_player_snapshot(payload)
    _LAST_PLAYER_SNAPSHOT_WRITE = now
    _PLAYER_SNAPSHOT_DIRTY = False
    _prune_player_cache()


def _player_state_payload() -> Optional[Dict[str, Any]]:
    if not _PLAYER_CACHE:
        return None
    entries = []
    online = 0
    for entry in _sorted_player_entries():
        summary = {
            "steam_id": entry.get("steam_id") or "",
            "name": entry.get("name") or entry.get("steam_id") or "Unknown",
            "online_state": entry.get("online_state")
            or ("online" if entry.get("online") else "offline"),
            "verified_by_api": bool(entry.get("verified_by_api")),
            "last_seen": entry.get("last_seen"),
            "current_character_id": entry.get("current_character_id"),
            "in_character_select": bool(entry.get("in_character_select")),
            "last_log_event": entry.get("last_log_event"),
            "last_http_event": entry.get("last_http_event"),
        }
        if summary["online_state"] != "offline":
            online += 1
        entries.append(summary)
    return {
        "schema_version": 1,
        "total": len(entries),
        "online": online,
        "entries": entries,
    }


def _extract_steam_id_from_line(line: str, name: Optional[str] = None) -> Optional[str]:
    for rx in (RX_SOCKET_STEAMID, RX_AUTH_SESSION_END, RX_PLAYER_STATE_ID):
        match = rx.search(line)
        if match:
            steam_id = match.group(1).strip()
            _remember_identity(steam_id, name)
            return steam_id
    return _lookup_id_for_name(name)


def _write_player_snapshot(payload: Dict[str, Any]) -> None:
    try:
        PLAYER_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PLAYER_SNAPSHOT_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
    except Exception:
        pass


def _set_http_state(state: Optional[Dict[str, Any]]) -> None:
    global _HTTP_STATE
    _HTTP_STATE = state


def _update_player_character_snapshot(
    snapshot: Dict[str, Any], client: VeinHTTPClient, errors: List[str]
) -> None:
    status_payload = snapshot.get("status") if isinstance(snapshot, dict) else {}
    online_players: Dict[str, Any] = {}
    if isinstance(status_payload, dict):
        raw = status_payload.get("onlinePlayers") or {}
        if isinstance(raw, dict):
            online_players = raw

    seen_ids: set[str] = set()
    fetch_errors = errors

    for steam_id, info in online_players.items():
        if not isinstance(info, dict):
            continue
        sid = str(steam_id)
        name = info.get("name")
        _remember_identity(sid, name)
        entry = _ensure_player_entry(sid, name)
        if not entry:
            continue

        previously_online = entry.get("online")
        entry["status"] = info.get("status") or entry.get("status")
        entry["time_connected"] = info.get("timeConnected")
        entry["http"] = info
        entry["verified_by_api"] = True
        entry["last_http_event"] = snapshot.get("last_fetch") or _utc_now_iso()
        entry["last_seen"] = entry["last_http_event"]
        char_id = info.get("characterId")
        if char_id:
            entry["current_character_id"] = char_id
            entry["in_character_select"] = False
            entry["online_state"] = "online"
            entry["online"] = True
        else:
            entry["in_character_select"] = True
            entry["online_state"] = "select"
            entry["online"] = True

        if not previously_online:
            state_hint = "select" if entry.get("in_character_select") else "online"
            _record_player_event(
                sid,
                "http_online",
                source="http",
                name=name,
                detail="HTTP API reports player online",
                state=state_hint,
            )

        try:
            player_detail = client.player(sid)
            entry["player"] = player_detail
        except VeinHTTPAPIError as exc:
            msg = f"player:{sid}: {exc}"
            fetch_errors.append(msg)
            _log_http_api(msg)
            continue
        except Exception as exc:  # pragma: no cover - defensive
            msg = f"player:{sid}: {exc}"
            fetch_errors.append(msg)
            _log_http_api(msg)
            continue

        characters_out: list[Dict[str, Any]] = []
        char_ids: list[str] = []
        if isinstance(player_detail, dict):
            raw_ids = player_detail.get("characterIds")
            if isinstance(raw_ids, list):
                char_ids = [str(cid) for cid in raw_ids]
        for char_id in char_ids:
            try:
                char_detail = client.character(char_id)
            except VeinHTTPAPIError as exc:
                msg = f"character:{char_id}: {exc}"
                fetch_errors.append(msg)
                _log_http_api(msg)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                msg = f"character:{char_id}: {exc}"
                fetch_errors.append(msg)
                _log_http_api(msg)
                continue
            char_entry: Dict[str, Any] = {
                "character_id": char_id,
                "name": None,
                "data": char_detail,
            }
            if isinstance(char_detail, dict):
                char_entry["name"] = (
                    (char_detail.get("characterData") or {}).get("name")
                    if isinstance(char_detail.get("characterData"), dict)
                    else (char_detail.get("playerCharacterData") or {}).get("name")
                )
            characters_out.append(char_entry)

        entry["characters"] = characters_out
        seen_ids.add(sid)

    for cache_key, entry in list(_PLAYER_CACHE.items()):
        sid = entry.get("steam_id") or cache_key
        if not sid or not sid.isdigit():
            continue
        if entry.get("verified_by_api") and entry.get("online") and sid not in seen_ids:
            _record_player_event(
                sid,
                "http_offline",
                source="http",
                detail="HTTP API reports player offline",
                state="offline",
            )
            entry["online"] = False
            entry["online_state"] = "offline"
            entry["in_character_select"] = False

    _flush_player_snapshot_if_needed(force=True, errors=fetch_errors)


def _refresh_http_api_state(client: VeinHTTPClient) -> None:
    snapshot: Dict[str, Any] = {"enabled": True}
    errors: list[str] = []

    def _call(key: str, func) -> None:
        try:
            snapshot[key] = func()
        except VeinHTTPAPIError as exc:
            msg = f"{key} request failed: {exc}"
            errors.append(msg)
            _log_http_api(msg)
        except Exception as exc:  # pragma: no cover - defensive
            msg = f"{key} unexpected error: {exc}"
            errors.append(msg)
            _log_http_api(msg)

    _call("status", client.status)
    _call("players", client.players)
    _call("time", client.time)
    _call("weather", client.weather)

    snapshot["last_fetch"] = _utc_now_iso()
    if errors:
        snapshot["errors"] = errors
    _set_http_state(snapshot)
    _update_player_character_snapshot(snapshot, client, errors)

def _write_logmon_state(
    *,
    active: bool,
    tailing_file: str | None,
    watching_server: bool,
) -> None:
    rp = _runtime_paths()
    rp["state_log"].parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "active": bool(active),
        "tailing_file": tailing_file,
        "watching_server": bool(watching_server),
        "last_updated": now,  # ISO8601 with tzinfo
    }
    if _HTTP_STATE is not None:
        data["http_api"] = _HTTP_STATE
    players_block = _player_state_payload()
    if players_block:
        data["players"] = players_block
    try:
        with rp["state_log"].open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception:
        pass


def _write_pid() -> None:
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def _clear_pid() -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def monitor() -> None:
    global _HTTP_DISABLED_LOGGED
    rp = _runtime_paths()
    stop_flag = rp["stop_log"]

    # announce + write pid once
    _write_pid()
    _write_logmon_state(active=False, tailing_file=None, watching_server=False)

    # cooldowns to avoid spammy loops
    last_hb = 0.0
    last_status_announce = 0.0
    last_down_announce = 0.0
    last_attach_announce = 0.0

    current_path: Path | None = None
    pos = 0

    ready_announced = False
    current_players: set[str] = set()
    last_autosave_ts = 0.0
    last_lastplayer_ts = 0.0
    last_crash_ts = 0.0
    seen_server_up_once = False
    last_seen_server_up = 0.0
    shutdown_backup_done = False
    http_client: Optional[VeinHTTPClient] = None
    last_http_refresh = 0.0
    http_refresh_interval = max(STATE_REFRESH_S, 5)
    http_pause_logged = False

    if TRACK_HTTP_API:
        try:
            http_client = get_configured_client()
        except Exception:
            http_client = None

        if http_client is None:
            _set_http_state(
                {
                    "enabled": False,
                    "last_error": "Vein HTTP API disabled or not configured.",
                }
            )
            if not _HTTP_DISABLED_LOGGED:
                _log_http_api("HTTP API disabled or misconfigured; polling skipped.")
                _HTTP_DISABLED_LOGGED = True
            _write_player_snapshot(
                {
                    "schema_version": 2,
                    "last_updated": _utc_now_iso(),
                    "players": [],
                    "admins": [],
                    "errors": ["Vein HTTP API disabled or not configured."],
                }
            )
        else:
            _set_http_state({"enabled": True, "last_fetch": None})
            _HTTP_DISABLED_LOGGED = False
    else:
        _set_http_state(None)
        _write_player_snapshot(
            {
                "schema_version": 2,
                "last_updated": _utc_now_iso(),
                "players": [],
                "admins": [],
                "errors": ["HTTP API tracking disabled via config."],
            }
        )

    def _server_up_recent(now_ts: float) -> bool:
        if not seen_server_up_once:
            return False
        return (now_ts - last_seen_server_up) <= max(http_refresh_interval * 2, 30)

    def _maybe_refresh_http_api(ts: Optional[float] = None) -> None:
        nonlocal last_http_refresh, http_pause_logged
        if not http_client:
            return
        now_ts = ts if ts is not None else time.time()
        if not _server_up_recent(now_ts):
            if not http_pause_logged:
                _log_http_api(
                    "HTTP API polling paused: server not running or not ready."
                )
                http_pause_logged = True
            return
        http_pause_logged = False
        if now_ts - last_http_refresh >= http_refresh_interval:
            _refresh_http_api_state(http_client)
            last_http_refresh = now_ts

    # rotation signature
    def _sig(p: Path) -> tuple[int, float]:
        st = p.stat()
        return (st.st_size, st.st_mtime)

    try:
        while True:
            # External stop request
            if stop_flag.exists():
                if NOTIFY_STATUS:
                    _discord(
                        "🛑 Log monitor stop flag detected; exiting.", channel="monitor"
                    )
                break

            # Re-resolve log if none
            p = current_path
            if not p or not p.exists():
                p = _resolve_active_log()
                if p and p.exists():
                    current_path = p
                    pos = 0
                    last_sig = None
                    if NOTIFY_STATUS:
                        _discord(
                            f"📜 Log monitor attached to `{p.name}`", channel="monitor"
                        )
                    last_attach_announce = time.time()
                else:
                    # No log yet; optionally linger and announce occasionally
                    now = time.time()
                    proc_up = is_server_running()
                    if not proc_up and not LINGER_WHEN_SERVER_DOWN:
                        if NOTIFY_STATUS and (now - last_down_announce > 30):
                            _discord(
                                "⏹ Server not running; log monitor idling.",
                                channel="monitor",
                            )
                            last_down_announce = now
                        _write_logmon_state(
                            active=False, tailing_file=None, watching_server=False
                        )
                        time.sleep(1.0)
                        continue

                    if now - last_down_announce > 20:
                        _discord(
                            "⏳ Waiting for Vein log file to appear…", channel="monitor"
                        )
                        last_down_announce = now

                    _write_logmon_state(
                        active=False, tailing_file=None, watching_server=False
                    )
                    time.sleep(1.0)
                    continue

            # Have a path; follow rotations/rewrites
            try:
                with p.open("rb") as f:
                    # Seek to last known position
                    f.seek(pos)
                    b = f.read(64 * 1024)
                    if not b:
                        # nothing new, small sleep
                        _write_logmon_state(
                            active=True,
                            tailing_file=str(p),
                            watching_server=True,
                        )
                        _maybe_refresh_http_api()
                        time.sleep(TAIL_POLL_MS / 1000.0)
                        continue
                    pos = f.tell()
            except FileNotFoundError:
                # rotation mid-read; retry next loop
                time.sleep(0.3)
                continue

            _write_logmon_state(active=True, tailing_file=str(p), watching_server=True)
            text = b.decode("utf-8", "replace")
            now = time.time()
            _maybe_refresh_http_api(now)

            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue

                if TRACK_JOIN and RX_LOGIN.search(line):
                    details = RX_LOGIN_NAME_ID.search(line)
                    if details:
                        login_name = details.group(1).strip()
                        login_id = details.group(2).strip()
                        _remember_identity(login_id, login_name)
                        _record_player_event(
                            login_id,
                            "login_request",
                            source="log",
                            name=login_name,
                            detail="Login request detected",
                            raw_line=line,
                            state="connecting",
                        )

                # Heartbeat (coarse)
                if (
                    TRACK_HEARTBEAT
                    and NOTIFY_HB
                    and (now - last_hb > HEARTBEAT_INTERVAL_S)
                ):
                    last_hb = now
                    _discord(
                        f"{_MONITOR_HB_PREFIX} Log monitor heartbeat — still tailing `{p.name}`",
                        channel="monitor",
                    )

                # Ready / joinable (world up + listening)
                if TRACK_STARTUP:
                    if RX_LISTEN.search(line) or RX_WORLD_UP.search(line):
                        if not ready_announced:
                            ready_announced = True
                            seen_server_up_once = True
                            last_seen_server_up = now
                            if NOTIFY_STARTUP or NOTIFY_JOINABLE:
                                _discord(
                                    "✅ Server reported ready / joinable in Vein.log.",
                                    channel="monitor",
                                )

                # Authenticated player ID (for future use)
                if TRACK_AUTH:
                    m = RX_AUTH_OK.search(line)
                    if m:
                        player_id = m.group(1)
                        _record_player_event(
                            player_id,
                            "authenticated",
                            source="log",
                            raw_line=line,
                            state="connecting",
                        )
                        if NOTIFY_AUTH:
                            _discord(
                                f"🔐 Authenticated player ID: {player_id}",
                                channel="monitor",
                            )
                    m_named = RX_PLAYER_AUTH_OK.search(line)
                    if m_named:
                        sid = m_named.group("steam")
                        _record_player_event(
                            sid,
                            "auth_confirmed",
                            source="log",
                            raw_line=line,
                            state="connecting",
                        )

                # Join / character select
                if TRACK_JOIN:
                    m = RX_JOINED.search(line)
                    if m:
                        name = m.group(1).strip()
                        current_players.add(name)
                        steam_id = _lookup_id_for_name(name)
                        _record_player_event(
                            steam_id,
                            "join",
                            source="log",
                            name=name,
                            detail=f"{name} joined world",
                            raw_line=line,
                            state="online",
                        )
                        if NOTIFY_JOIN:
                            _discord(
                                f"🚪 Player joined: **{name}**",
                                channel="monitor",
                            )

                if TRACK_CHARACTER:
                    m = RX_CHARSEL.search(line)
                    if m and NOTIFY_CHARACTER:
                        aka = m.group(1).strip()
                        _discord(
                            f"🎭 Character selected: **{aka}**",
                            channel="monitor",
                        )
                    full = RX_CHARSEL_FULL.search(line)
                    if full:
                        pname = full.group("name").strip()
                        cid = full.group("char").strip()
                        steam_id = _lookup_id_for_name(pname)
                        _record_player_event(
                            steam_id,
                            "character_select",
                            source="log",
                            name=pname,
                            character_id=cid,
                            detail=f"{pname} selected character {cid}",
                            raw_line=line,
                            state="online",
                        )

                # Disconnect
                if TRACK_DISCONNECT and RX_DISC.search(line):
                    steam_id = _extract_steam_id_from_line(line)
                    if steam_id:
                        _record_player_event(
                            steam_id,
                            "disconnect",
                            source="log",
                            raw_line=line,
                            state="offline",
                        )
                    if NOTIFY_DISC:
                        _discord("👋 Player disconnected.", channel="monitor")

                # Autosave backups
                if AUTOSAVE_ENABLED and TRACK_AUTOSAVE and RX_AUTOSAVE.search(line):
                    if now - last_autosave_ts >= AUTOSAVE_COOLDOWN:
                        last_autosave_ts = now
                        if NOTIFY_AUTOSAVE:
                            _discord(
                                "💾 Autosave detected; creating backup…",
                                channel="monitor",
                            )
                        try:
                            backup_save_file(reason="Autosave")
                        except Exception:
                            pass

                # Crash detection + backup
                if CRASH_ENABLED and TRACK_CRASH and RX_CRASH.search(line):
                    if now - last_crash_ts >= CRASH_DEBOUNCE:
                        last_crash_ts = now
                        if NOTIFY_CRASH:
                            _discord(
                                "💥 Crash detected in Vein.log — creating backup…",
                                channel="monitor",
                            )
                        _backup("Crash")

            _flush_player_snapshot_if_needed()

            # Linger + shutdown backup check
            proc_up = is_server_running()
            if proc_up:
                seen_server_up_once = True
                last_seen_server_up = now

            if SHUT_ENABLED and SHUTDOWN_FLAG.exists():
                try:
                    flag_mtime = SHUTDOWN_FLAG.stat().st_mtime
                    flag_fresh = (now - flag_mtime) <= SHUT_GRACE
                except Exception:
                    flag_fresh = False

                proc_down = not proc_up
                if (
                    proc_down
                    and flag_fresh
                    and seen_server_up_once
                    and not shutdown_backup_done
                ):
                    _backup("Shutdown")
                    shutdown_backup_done = True

    finally:
        _write_logmon_state(active=False, tailing_file=None, watching_server=False)
        _flush_player_snapshot_if_needed(force=True)
        _clear_pid()


if __name__ == "__main__":
    monitor()
