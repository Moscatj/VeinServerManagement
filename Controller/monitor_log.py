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
from datetime import datetime
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
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "active": bool(active),
        "tailing_file": tailing_file,
        "watching_server": watching_server,
        "source": "monitor_log.py",
        "headless": current_headless_flag(),
    }
    _atomic_write_json(LOG_MON_STATE, payload)


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
    _write_logmon_state(active=False, tailing_file=None, watching_server=None)
    try:
        if NOTIFY_STATUS:
            _discord("🟡 Log monitor starting…", channel="monitor")

        # Wait for log file to appear
        start_time = time.time()
        log_file: Optional[Path] = _pick_log_file()
        while not log_file or not log_file.exists():
            if STOP_FLAG.exists():
                _write_logmon_state(active=False, tailing_file=None, watching_server=False)
                if NOTIFY_STATUS:
                    _discord("🛑 Log monitor stop requested; exiting.", channel="monitor")
                return
            if time.time() - start_time > WAIT_FOR_LOG_S:
                if NOTIFY_STATUS:
                    _discord("⚠️ No Vein log file found; exiting log monitor.", channel="monitor")
                return
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

        with log_file.open("r", encoding="utf-8", errors="ignore") as f:
            # pre-read existing until EOF, then tail
            for _ in f:
                pass
            for line in tail_log(f):  # ← single loop
                if STOP_FLAG.exists():
                    _write_logmon_state(active=False, tailing_file=str(log_file), watching_server=False)
                    if NOTIFY_STATUS:
                        _discord("🛑 Log monitor stop requested; exiting.", channel="monitor")
                    break

                running_server = is_server_running()
                now = time.time()

                # --- idle tick: keep state fresh even when Vein.log is quiet
                if line is None:
                    if (now - last_state_ts) >= STATE_REFRESH_S:
                        last_state_ts = now
                        _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=running_server)

                    if TRACK_HEARTBEAT and HEARTBEAT_INTERVAL_S > 0 and (now - last_hb_ts) >= HEARTBEAT_INTERVAL_S:
                        last_hb_ts = now
                        _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=running_server)
                        if NOTIFY_HB:
                            _discord("🫀 Log monitor heartbeat.", channel="monitor")
                    continue

                # --- from here on, we have a REAL log line ---

                # bail out if server gone
                if not running_server:
                    _write_logmon_state(active=False, tailing_file=str(log_file), watching_server=False)
                    if NOTIFY_STATUS:
                        _discord("🛑 Server process ended; stopping log monitor.", channel="monitor")
                    break

                # cheap state refresh independent of Discord/heartbeat
                if (now - last_state_ts) >= STATE_REFRESH_S:
                    last_state_ts = now
                    _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=True)

                # ---- Ready/Joinable detection
                if TRACK_STARTUP:
                    if RX_LISTEN.search(line) or RX_WORLD_UP.search(line) or RX_STEAM_OK.search(line):
                        if not ready_announced:
                            ready_announced = True
                            if NOTIFY_STARTUP or NOTIFY_JOINABLE:
                                _discord("✅ Server is up and joinable.", channel="monitor")

                # ---- Player auth/login
                m_auth = RX_AUTH_OK.search(line) if TRACK_AUTH else None
                if m_auth and NOTIFY_AUTH:
                    steam_id = m_auth.group(1)
                    _discord(f"🔐 Auth OK for `{steam_id}`.", channel="monitor")

                m_join = RX_JOINED.search(line) if TRACK_JOIN else None
                if m_join:
                    name = m_join.group(1).strip()
                    current_players.add(name)
                    if NOTIFY_JOIN:
                        _discord(f"➡️ `{name}` joined.", channel="monitor")

                m_char = RX_CHARSEL.search(line) if TRACK_CHARACTER else None
                if m_char and NOTIFY_CHARACTER:
                    name = m_char.group(1).strip()
                    _discord(f"🎭 `{name}` selected a character.", channel="monitor")

                if TRACK_DISCONNECT and RX_DISC.search(line):
                    if NOTIFY_DISC:
                        _discord("⬅️ A player disconnected.", channel="monitor")

                # ---- Autosave → optional backup (debounced)
                if TRACK_AUTOSAVE and RX_AUTOSAVE.search(line):
                    cooldown = int(config.get("autosave_backup_cooldown_seconds", 300))
                    if BACKUPS.get("on_autosave", True) and (now - last_autosave_ts) > cooldown:
                        last_autosave_ts = now
                        try:
                            backup_save_file(None, reason="AutoSave")
                            if NOTIFY_AUTOSAVE:
                                _discord("💾 Autosave detected — backup created.", channel="monitor")
                        except Exception:
                            pass

                # ---- Crash signatures
                if TRACK_CRASH and RX_CRASH.search(line):
                    if NOTIFY_CRASH:
                        _discord("💥 Crash signature in log! Check server.", channel="monitor")

                # (Optional) heartbeat also on real lines if you prefer:
                if TRACK_HEARTBEAT and HEARTBEAT_INTERVAL_S > 0 and (now - last_hb_ts) >= HEARTBEAT_INTERVAL_S:
                    last_hb_ts = now
                    _write_logmon_state(active=True, tailing_file=str(log_file), watching_server=running_server)
                    if NOTIFY_HB:
                        _discord("🫀 Log monitor heartbeat.", channel="monitor")


    finally:
        _write_logmon_state(active=False, tailing_file=None, watching_server=False)
        _clear_pid_file()

if __name__ == "__main__":
    monitor()
