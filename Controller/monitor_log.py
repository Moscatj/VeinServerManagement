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

    # Vein/Saved/Logs (EA/Demo layouts)
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
        except Exception:
            continue

    return newest[1] if newest else None

def _runtime_paths() -> dict:
    """
    Returns the paths this monitor uses inside Runtime/.
    Keys match what the GUI StatusPoller expects: 'state_log' and 'pid_log'.
    """
    # Prefer config["runtime_dir"]; fall back to repo/Runtime
    base = Path(
        (config.get("runtime_dir") or "")  # type: ignore[name-defined]
    ).expanduser()
    if not str(base):
        base = Path(__file__).parents[1] / "Runtime"

    # Ensure the directory exists
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

# ---------------------------------------------------------------------------
# Helpers near the top of file (keep or add if missing):
# from datetime import datetime, timezone
# def _discord(msg: str, channel: str = "monitor"): ...
# def _runtime_paths(): ...  # returns dict with 'state_log', 'stop_log', 'pid_log', etc.
# def _resolve_active_log() -> Path: ...  # returns the current Vein.log path
# RX_* patterns exist above (RX_LISTEN, RX_JOINED, etc.)
# ---------------------------------------------------------------------------

def _write_logmon_state(*, active: bool, tailing_file: str | None, watching_server: bool) -> None:
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
            json.dump(data, f)
    except Exception:
        pass

def _write_pid() -> None:
    rp = _runtime_paths()
    try:
        rp["pid_log"].write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

def _clear_pid() -> None:
    rp = _runtime_paths()
    try:
        if rp["pid_log"].exists():
            rp["pid_log"].unlink()
    except Exception:
        pass


def monitor() -> None:
    rp = _runtime_paths()
    stop_flag = rp["stop_log"]

    # announce + write pid once
    _write_pid()
    _write_logmon_state(active=False, tailing_file=None, watching_server=False)

    # cooldowns to avoid spammy loops
    last_down_announce   = 0.0
    last_attach_announce = 0.0

    current_path: Path | None = None
    pos = 0

    # Match toggles
    TRACK_STARTUP    = bool(config.get("monitor", {}).get("track", {}).get("startup", True))
    TRACK_JOIN       = bool(config.get("monitor", {}).get("track", {}).get("join", True))
    TRACK_AUTH       = bool(config.get("monitor", {}).get("track", {}).get("auth", True))
    TRACK_CHARACTER  = bool(config.get("monitor", {}).get("track", {}).get("character", True))
    TRACK_DISCONNECT = bool(config.get("monitor", {}).get("track", {}).get("disconnect", True))
    TRACK_AUTOSAVE   = bool(config.get("monitor", {}).get("track", {}).get("autosave", True))
    TRACK_CRASH      = bool(config.get("monitor", {}).get("track", {}).get("crash", True))

    NOTIFY_STARTUP   = bool(config.get("monitor", {}).get("notify", {}).get("startup", True))
    NOTIFY_JOIN      = bool(config.get("monitor", {}).get("notify", {}).get("join", True))
    NOTIFY_AUTH      = bool(config.get("monitor", {}).get("notify", {}).get("auth", False))
    NOTIFY_CHARACTER = bool(config.get("monitor", {}).get("notify", {}).get("character", False))
    NOTIFY_DISC      = bool(config.get("monitor", {}).get("notify", {}).get("disconnect", True))
    NOTIFY_AUTOSAVE  = bool(config.get("monitor", {}).get("notify", {}).get("autosave", True))
    NOTIFY_CRASH     = bool(config.get("monitor", {}).get("notify", {}).get("crash", True))
    NOTIFY_JOINABLE  = True  # piggyback ready message if desired

    ready_announced = False
    current_players: set[str] = set()
    last_autosave_ts = 0.0

    # rotation signature
    def _sig(p: Path) -> tuple[int, float]:
        st = p.stat()
        return (st.st_size, st.st_mtime)

    last_sig: tuple[int, float] | None = None

    try:
        while not stop_flag.exists():
            p = _resolve_active_log()

            # If no log yet, go into a quiet linger loop (announce at most every 20s)
            if not p or not p.exists():
                now = time.time()
                if now - last_down_announce > 20:
                    _discord("⏳ Server down — lingering. Will reattach when new log appears.", channel="monitor")
                    last_down_announce = now
                _write_logmon_state(active=False, tailing_file=None, watching_server=False)
                time.sleep(1.0)
                continue

            # Reattach announcement only when path actually changes
            if str(p) != str(current_path):
                current_path = p
                pos = 0
                last_sig = None
                now = time.time()
                if now - last_attach_announce > 10:
                    _discord(f"🔁 Reattached to {p.name}.", channel="monitor")
                    last_attach_announce = now

            # Detect rotation/truncate by signature change to smaller size/mtime backwards
            try:
                sig = _sig(p)
                if last_sig is not None:
                    size, mt = sig
                    old_size, old_mt = last_sig
                    if size < old_size or (mt != old_mt and size < old_size):
                        # rotation/truncate – reopen from start
                        pos = 0
                last_sig = sig
            except FileNotFoundError:
                # file vanished between exists() and stat(); loop will re-check
                time.sleep(0.5)
                continue

            # Tail a chunk
            try:
                with p.open("rb") as f:
                    f.seek(pos)
                    b = f.read(262144)
                    if not b:
                        # idle cycle
                        _write_logmon_state(active=True, tailing_file=str(p), watching_server=True)
                        time.sleep(0.3)
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

                # --- READY/JOINABLE SIGNS ---
                if TRACK_STARTUP:
                    if RX_LISTEN.search(line) or RX_WORLD_UP.search(line) or RX_STEAM_OK.search(line):
                        if not ready_announced:
                            ready_announced = True
                            if NOTIFY_STARTUP or NOTIFY_JOINABLE:
                                _discord("✅ Server is up and joinable.", channel="monitor")

                # --- AUTH OK ---
                if TRACK_AUTH:
                    m = RX_AUTH_OK.search(line)
                    if m and NOTIFY_AUTH:
                        _discord(f"🔐 Auth OK for `{m.group(1)}`.", channel="monitor")

                # --- PLAYER JOIN ---
                if TRACK_JOIN:
                    m = RX_JOINED.search(line)
                    if m:
                        name = m.group(1).strip()
                        current_players.add(name)
                        if NOTIFY_JOIN:
                            _discord(f"➡️ `{name}` joined.", channel="monitor")

                # --- CHARACTER SELECT ---
                if TRACK_CHARACTER:
                    m = RX_CHARSEL.search(line)
                    if m and NOTIFY_CHARACTER:
                        _discord(f"🎭 `{m.group(1).strip()}` selected a character.", channel="monitor")

                # --- DISCONNECT ---
                if TRACK_DISCONNECT and RX_DISC.search(line):
                    if NOTIFY_DISC:
                        _discord("⬅️ A player disconnected.", channel="monitor")

                # --- AUTOSAVE/BACKUP ---
                if TRACK_AUTOSAVE and RX_AUTOSAVE.search(line):
                    cooldown = int(config.get("autosave_backup_cooldown_seconds", 300))
                    if (now - last_autosave_ts) > cooldown:
                        last_autosave_ts = now
                        try:
                            backup_save_file(None, reason="AutoSave")
                            if NOTIFY_AUTOSAVE:
                                _discord("💾 Autosave detected — backup created.", channel="monitor")
                        except Exception:
                            pass

                # --- CRASH SIGNATURE ---
                if TRACK_CRASH and RX_CRASH.search(line):
                    if NOTIFY_CRASH:
                        _discord("💥 Crash signature in log! Check server.", channel="monitor")

    finally:
        _write_logmon_state(active=False, tailing_file=None, watching_server=False)
        _clear_pid()

if __name__ == "__main__":
    monitor()

