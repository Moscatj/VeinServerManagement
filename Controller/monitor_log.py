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
from glob import glob

from Tools import backups as _bk

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

HEARTBEAT_INTERVAL_S      = int(
    _MON.get(
        "heartbeat_interval_seconds",
        config.get("monitor_heartbeat_interval_seconds", 300),
    )
)
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

RX_CRASH    = re.compile(
    r"Fatal error|Access violation|EXCEPTION_ACCESS_VIOLATION|Assertion failed|ensure\(!\)",
    re.I,
)

_BEH = dict((_MON.get("heartbeat", {}) or {}))

_MONITOR_HB_CHANNEL = str(_BEH.get("channel", "monitor"))
_MONITOR_HB_PREFIX  = str(_BEH.get("prefix", "🩺"))

# Backups events section
_BEV = dict((config.get("backups", {}) or {}).get("events", {}) or {})

_EVT_AUTOSAVE = dict(_BEV.get("autosave", {}) or {})
_EVT_LAST    = dict(_BEV.get("last_player", {}) or {})
_EVT_CRASH   = dict(_BEV.get("crash", {}) or {})
_EVT_SHUT    = dict(_BEV.get("shutdown", {}) or {})

AUTOSAVE_ENABLED   = bool(_EVT_AUTOSAVE.get("enabled", True))
AUTOSAVE_COOLDOWN  = int(
    _EVT_AUTOSAVE.get(
        "cooldown_seconds",
        int(config.get("autosave_backup_cooldown_seconds", 300)),
    )
)

LAST_ENABLED       = bool(_EVT_LAST.get("enabled", True))
LAST_COOLDOWN      = int(_EVT_LAST.get("cooldown_seconds", 600))

CRASH_ENABLED      = bool(_EVT_CRASH.get("enabled", True))
CRASH_DEBOUNCE     = int(_EVT_CRASH.get("debounce_seconds", 120))

SHUT_ENABLED       = bool(_EVT_SHUT.get("enabled", True))
SHUT_GRACE         = int(_EVT_SHUT.get("grace_seconds", 900))

# shutdown flag (we re-create the same path utils uses)
SHUTDOWN_FLAG = RUNTIME_DIR / "shutdown_in_progress.flag"


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
        "runtime":    base,
        "state_log":  base / "log_monitor.state.json",  # GUI reads this
        "pid_log":    base / "log_monitor.pid",         # GUI checks this
        "stop_log":   base / "log_monitor.stop",        # touch this to stop monitor
    }


def _discord(msg: str, channel: str = "monitor"):
    if is_discord_channel_enabled(channel):
        send_discord_message(msg, channel=channel)


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
        "last_updated": now,   # ISO8601 with tzinfo
    }
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
    rp = _runtime_paths()
    stop_flag = rp["stop_log"]

    # announce + write pid once
    _write_pid()
    _write_logmon_state(active=False, tailing_file=None, watching_server=False)

    # cooldowns to avoid spammy loops
    last_hb = 0.0
    last_status_announce = 0.0
    last_down_announce   = 0.0
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

    # rotation signature
    def _sig(p: Path) -> tuple[int, float]:
        st = p.stat()
        return (st.st_size, st.st_mtime)

    try:
        while True:
            # External stop request
            if stop_flag.exists():
                if NOTIFY_STATUS:
                    _discord("🛑 Log monitor stop flag detected; exiting.", channel="monitor")
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
                        _discord(f"📜 Log monitor attached to `{p.name}`", channel="monitor")
                    last_attach_announce = time.time()
                else:
                    # No log yet; optionally linger and announce occasionally
                    now = time.time()
                    proc_up = is_server_running()
                    if not proc_up and not LINGER_WHEN_SERVER_DOWN:
                        if NOTIFY_STATUS and (now - last_down_announce > 30):
                            _discord("⏹ Server not running; log monitor idling.", channel="monitor")
                            last_down_announce = now
                        _write_logmon_state(active=False, tailing_file=None, watching_server=False)
                        time.sleep(1.0)
                        continue

                    if now - last_down_announce > 20:
                        _discord("⏳ Waiting for Vein log file to appear…", channel="monitor")
                        last_down_announce = now

                    _write_logmon_state(active=False, tailing_file=None, watching_server=False)
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

            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue

                # Heartbeat (coarse)
                if TRACK_HEARTBEAT and NOTIFY_HB and (now - last_hb > HEARTBEAT_INTERVAL_S):
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
                    if m and NOTIFY_AUTH:
                        player_id = m.group(1)
                        _discord(
                            f"🔐 Authenticated player ID: {player_id}",
                            channel="monitor",
                        )

                # Join / character select
                if TRACK_JOIN:
                    m = RX_JOINED.search(line)
                    if m:
                        name = m.group(1).strip()
                        current_players.add(name)
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

                # Disconnect
                if TRACK_DISCONNECT and RX_DISC.search(line):
                    if NOTIFY_DISC:
                        _discord("👋 Player disconnected.", channel="monitor")

                # Autosave backups
                if AUTOSAVE_ENABLED and TRACK_AUTOSAVE and RX_AUTOSAVE.search(line):
                    if now - last_autosave_ts >= AUTOSAVE_COOLDOWN:
                        last_autosave_ts = now
                        if NOTIFY_AUTOSAVE:
                            _discord("💾 Autosave detected; creating backup…", channel="monitor")
                        try:
                            backup_save_file(reason="Autosave")
                        except Exception:
                            pass

                # Crash detection + backup
                if CRASH_ENABLED and TRACK_CRASH and RX_CRASH.search(line):
                    if now - last_crash_ts >= CRASH_DEBOUNCE:
                        last_crash_ts = now
                        if NOTIFY_CRASH:
                            _discord("💥 Crash detected in Vein.log — creating backup…", channel="monitor")
                        _backup("Crash")

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
        _clear_pid()


if __name__ == "__main__":
    monitor()
