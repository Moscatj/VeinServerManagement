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
from typing import Optional

from utils import (
    config,
    LOGS_DIR,
    ABSOLUTE_LOG_FILE,
    RUNTIME_DIR,
    is_server_running,
    send_discord_message,
    is_discord_channel_enabled,
    backup_save_file,
    current_headless_flag,
)

PID_FILE = RUNTIME_DIR / "log_monitor.pid"

# ---- Config knobs (with sensible defaults) ----
_MON = dict(config.get("monitor", {}))
TRACK      = dict(_MON.get("track", {}))
BACKUPS    = dict(_MON.get("backups", {}))
NOTIFY     = dict(_MON.get("notify", {}))
STATE_REFRESH_S = int(_MON.get("state_refresh_seconds", 15))
LINGER_WHEN_SERVER_DOWN = bool(_MON.get("linger_when_server_down", True))
RECHECK_NEWEST_EVERY_S  = int(_MON.get("recheck_newest_every_seconds", 5))

LOG_MON_STATE = RUNTIME_DIR / "log_monitor_state.json"
STOP_FLAG = RUNTIME_DIR / "stop_log_monitor.flag"

HEARTBEAT_INTERVAL_S      = int(_MON.get("heartbeat_interval_seconds", config.get("monitor_heartbeat_interval_seconds", 300)))
WAIT_FOR_LOG_S            = int(_MON.get("wait_for_log_appearance_seconds", 120))
TAIL_POLL_MS              = int(_MON.get("tail_poll_interval_ms", 500))

TRACK_STARTUP    = bool(TRACK.get("startup", True))
TRACK_AUTH       = bool(TRACK.get("auth", True))
TRACK_JOIN       = bool(TRACK.get("join", True))
TRACK_CHARACTER  = bool(TRACK.get("character", True))
TRACK_DISCONNECT = bool(TRACK.get("disconnect", True))
TRACK_AUTOSAVE   = bool(TRACK.get("autosave", True))
TRACK_CRASH      = bool(TRACK.get("crash", True))
TRACK_HEARTBEAT  = bool(TRACK.get("heartbeat", True))

NOTIFY_STARTUP   = bool(NOTIFY.get("startup", True))
NOTIFY_JOINABLE  = bool(NOTIFY.get("joinable", True))
NOTIFY_AUTH      = bool(NOTIFY.get("auth", True))
NOTIFY_JOIN      = bool(NOTIFY.get("join", True))
NOTIFY_CHARACTER = bool(NOTIFY.get("character", True))
NOTIFY_DISC      = bool(NOTIFY.get("disconnect", True))
NOTIFY_AUTOSAVE  = bool(NOTIFY.get("autosave", False))
NOTIFY_CRASH     = bool(NOTIFY.get("crash", True))
NOTIFY_HB        = bool(NOTIFY.get("heartbeat", False))
NOTIFY_STATUS    = bool(NOTIFY.get("monitor_status", True))

# ---- Regex library tuned to real Vein.log lines ----
RX_LISTEN   = re.compile(r"RamjetSteamNetDriver_.*started listening on (\d+)", re.I)
RX_WORLD_UP = re.compile(r"LogWorld: Bringing World .* up for play", re.I)
RX_STEAM_OK = re.compile(r"Steamworks server initialized", re.I)

RX_LOGIN    = re.compile(r"LogNet: Login request:")  # (defined for future use)
RX_AUTH_OK  = re.compile(r"LogRamjetNetworking: Authenticated (\d+)")
RX_JOINED   = re.compile(r"LogNet: Join succeeded:\s*(.+)")
RX_CHARSEL  = re.compile(r"selected character .* \(aka ([^)]+)\)", re.I)
RX_DISC     = re.compile(r"closed by peer|Logout|Connection closed", re.I)

RX_AUTOSAVE = re.compile(r"LogVeinSaveGame: Saved save game to disk", re.I)

RX_CRASH    = re.compile(r"Fatal error|Access violation|EXCEPTION_ACCESS_VIOLATION|Assertion failed|ensure\(!\)", re.I)

def _atomic_write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def _write_logmon_state(active: bool, tailing_file: str | None = None, watching_server: bool | None = None):
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "active": bool(active),
        "tailing_file": tailing_file,
        "watching_server": watching_server,
        "source": "monitor_log.py",
        "headless": current_headless_flag(),
    }
    _atomic_write_json(LOG_MON_STATE, payload)

def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve().samefile(b.resolve())
    except Exception:
        return str(a) == str(b)

def _open_tail(path: Path) -> io.TextIOBase:
    f = path.open("r", encoding="utf-8", errors="ignore")
    # pre-drain to EOF so we only see new lines
    for _ in f:
        pass
    return f

def _pick_log_file() -> Optional[Path]:
    # Prefer absolute from config
    if ABSOLUTE_LOG_FILE:
        p = Path(ABSOLUTE_LOG_FILE)
        if p.exists():
            return p
    # Else pick newest Vein*.log from LOGS_DIR
    try:
        cands = sorted((LOGS_DIR.glob("Vein*.log")), key=lambda p: p.stat().st_mtime, reverse=True)
        return cands[0] if cands else None
    except Exception:
        return None

def _touch_pid_file():
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

def _clear_pid_file():
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def _discord(msg: str, channel: str = "monitor"):
    if is_discord_channel_enabled(channel):
        send_discord_message(msg, channel=channel)

def tail_log(fp: io.TextIOBase):
    """Yield new lines as they appear; yield None periodically when idle."""
    fp.seek(0, os.SEEK_END)
    poll = max(0.05, TAIL_POLL_MS / 1000.0)
    while True:
        line = fp.readline()
        if not line:
            time.sleep(poll)
            yield None            # <-- idle tick so we can run timers
            continue
        yield line.rstrip("\r\n")

def monitor():
    _touch_pid_file()
    # Clear any stale stop request from a previous session
    try:
        STOP_FLAG.unlink(missing_ok=True)
    except Exception:
        pass
        
    _write_logmon_state(active=False, tailing_file=None, watching_server=None)
    try:
        if NOTIFY_STATUS:
            _discord("🟡 Log monitor starting…", channel="monitor")

        # Wait for log file to appear
        start_time = time.time()
        log_file: Optional[Path] = _pick_log_file()
        warned = False
        last_state = 0.0

        while not log_file or not log_file.exists():
            if STOP_FLAG.exists():
                _write_logmon_state(active=False, tailing_file=None, watching_server=False)
                if NOTIFY_STATUS:
                    _discord("🛑 Log monitor stop requested; exiting.", channel="monitor")
                return

            # publish "inactive but watching" state every ~5s while waiting
            now = time.time()
            if now - last_state > 5:
                last_state = now
                _write_logmon_state(active=False, tailing_file=None, watching_server=is_server_running())

            # after the configured timeout, warn ONCE but DO NOT exit — keep waiting
            if (not warned) and (now - start_time > WAIT_FOR_LOG_S):
                warned = True
                if NOTIFY_STATUS:
                    _discord("⌛ No Vein log yet; continuing to wait and will attach when it appears.", channel="monitor")

            time.sleep(1)
            log_file = _pick_log_file()

        if NOTIFY_STATUS:
            _discord(f"📜 Monitoring `{log_file.name}`.", channel="monitor")

        # always set active, regardless of Discord settings
        _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=is_server_running())

        # announce fully active once, after setup
        if NOTIFY_STATUS:
            _discord("🟢 Log monitor is active and tracking Vein server logs.", channel="monitor")

        ready_announced = False
        last_autosave_ts = 0.0
        last_hb_ts = 0.0
        current_players: set[str] = set()
        last_state_ts = 0.0

        # resilient follow: reopen on rotation/truncation/newest-file change
        f = _open_tail(log_file)
        try:
            last_check = time.time()
            last_size = log_file.stat().st_size if log_file.exists() else 0

            while True:
                # cooperative stop
                if STOP_FLAG.exists():
                    _write_logmon_state(active=False, tailing_file=str(log_file), watching_server=False)
                    if NOTIFY_STATUS:
                        _discord("🛑 Log monitor stop requested; exiting.", channel="monitor")
                    break

                running_server = is_server_running()
                now = time.time()

                # periodically refresh state even when quiet
                line = f.readline()
                if not line:
                    time.sleep(max(0.05, TAIL_POLL_MS / 1000.0))
                    # idle tick house-keeping
                    _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=running_server)

                    # heartbeat (optional)
                    if TRACK_HEARTBEAT and HEARTBEAT_INTERVAL_S > 0 and (now - last_hb_ts) >= HEARTBEAT_INTERVAL_S:
                        last_hb_ts = now
                        if NOTIFY_HB:
                            _discord("🫀 Log monitor heartbeat.", channel="monitor")

                    # detect truncation (file got recreated) → seek to start
                    try:
                        cur_size = log_file.stat().st_size
                    except Exception:
                        cur_size = 0
                    if cur_size < last_size:
                        try:
                            f.close()
                        except Exception:
                            pass
                        f = _open_tail(log_file)
                        last_size = cur_size
                        if NOTIFY_STATUS:
                            _discord(f"♻️ Detected truncation; reattached `{log_file.name}` from start.", channel="monitor")

                    # every few seconds, check if a newer Vein*.log appeared
                    if (now - last_check) >= RECHECK_NEWEST_EVERY_S:
                        last_check = now
                        newest = _pick_log_file()
                        if newest and not _same_file(newest, log_file):
                            try:
                                f.close()
                            except Exception:
                                pass
                            log_file = newest
                            f = _open_tail(log_file)
                            _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=running_server)
                            if NOTIFY_STATUS:
                                _discord(f"📜 Switched to newest log: `{log_file.name}`.", channel="monitor")
                    continue

                # we have a real line
                line = line.rstrip("\r\n")
                last_size += len(line) + 1  # rough advance

                # server lifecycle
                if not running_server:
                    _write_logmon_state(active=False, tailing_file=str(log_file), watching_server=False)
                    if not LINGER_WHEN_SERVER_DOWN:
                        if NOTIFY_STATUS:
                            _discord("🛑 Server ended; stopping log monitor.", channel="monitor")
                        break
                    # linger: wait for a new log to appear and reattach
                    sleep_start = time.time()
                    if NOTIFY_STATUS:
                        _discord("⏳ Server down — lingering. Will reattach when new log appears.", channel="monitor")
                    while True:
                        if STOP_FLAG.exists():
                            break
                        log_file = _pick_log_file()
                        if log_file and log_file.exists():
                            try:
                                f.close()
                            except Exception:
                                pass
                            f = _open_tail(log_file)
                            _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=is_server_running())
                            if NOTIFY_STATUS:
                                _discord(f"🔁 Reattached to `{log_file.name}`.", channel="monitor")
                            break
                        if time.time() - sleep_start > WAIT_FOR_LOG_S:
                            # keep lingering; check again next loop
                            sleep_start = time.time()
                        time.sleep(1)
                    continue

                # cheap state refresh
                if (now - last_state_ts) >= STATE_REFRESH_S:
                    last_state_ts = now
                    _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=True)

                # ---- existing pattern matching and Discord sends below unchanged ----
                # (Ready/Join, Auth, Character, Disconnect, Autosave/Backup, Crash)
                # ... keep all your existing handling here ...
                if TRACK_STARTUP:
                    if RX_LISTEN.search(line) or RX_WORLD_UP.search(line) or RX_STEAM_OK.search(line):
                        if not ready_announced:
                            ready_announced = True
                            if NOTIFY_STARTUP or NOTIFY_JOINABLE:
                                _discord("✅ Server is up and joinable.", channel="monitor")

                m_auth = RX_AUTH_OK.search(line) if TRACK_AUTH else None
                if m_auth and NOTIFY_AUTH:
                    steam_id = m_auth.group(1); _discord(f"🔐 Auth OK for `{steam_id}`.", channel="monitor")

                m_join = RX_JOINED.search(line) if TRACK_JOIN else None
                if m_join:
                    name = m_join.group(1).strip()
                    current_players.add(name)
                    if NOTIFY_JOIN: _discord(f"➡️ `{name}` joined.", channel="monitor")

                m_char = RX_CHARSEL.search(line) if TRACK_CHARACTER else None
                if m_char and NOTIFY_CHARACTER:
                    name = m_char.group(1).strip(); _discord(f"🎭 `{name}` selected a character.", channel="monitor")

                if TRACK_DISCONNECT and RX_DISC.search(line):
                    if NOTIFY_DISC: _discord("⬅️ A player disconnected.", channel="monitor")

                if TRACK_AUTOSAVE and RX_AUTOSAVE.search(line):
                    cooldown = int(config.get("autosave_backup_cooldown_seconds", 300))
                    if BACKUPS.get("on_autosave", True) and (now - last_autosave_ts) > cooldown:
                        last_autosave_ts = now
                        try:
                            backup_save_file(None, reason="AutoSave")
                            if NOTIFY_AUTOSAVE: _discord("💾 Autosave detected — backup created.", channel="monitor")
                        except Exception:
                            pass

                if TRACK_CRASH and RX_CRASH.search(line):
                    if NOTIFY_CRASH: _discord("💥 Crash signature in log! Check server.", channel="monitor")

        finally:
            _write_logmon_state(active=False, tailing_file=None, watching_server=False)
            _clear_pid_file()


if __name__ == "__main__":
    monitor()
