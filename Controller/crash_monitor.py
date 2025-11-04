#!/usr/bin/env python3
"""
crash_monitor.py
Watches for unexpected server exits and triggers a controlled restart.

This version is refactored to rely on shared utils/config only:
- Paths, flags, and intervals pulled from config/config_helper
- Discord messages sent via utils.send_discord_message(...)
- Process detection via utils.find_running_server()
- Restart logic via utils.initiate_controlled_restart(...)
- Quiet windows via utils.startup_grace_active(...) and utils.autorestart_quiet_active(...)
- Intentional-shutdown suppression via utils.is_shutdown_in_progress()

Runtime artifacts:
  Runtime/crash_monitor.pid
  Runtime/crash_monitor_state.json
  Runtime/stop_crash_monitor.flag
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# Single source of truth for config/feature flags
from config_helper import config, is_feature_enabled

# Shared helpers & paths
from utils import (
    RUNTIME_DIR,
    STATE_FLAG,                       # Runtime/server_running.flag
    find_running_server,              # returns psutil.Process | None
    is_shutdown_in_progress,          # True if a managed shutdown is underway
    startup_grace_active,             # grace window after startup (sec)
    autorestart_quiet_active,         # global "quiet" window for auto-restarts
    initiate_controlled_restart,      # orchestrated stop->backup->start
    send_discord_message,             # posts to Discord w/ feature & channel gating
)

# === Config knobs (live, but read here for cadence) ===
MONITOR_INTERVAL_SEC   = int(config.get("crash_monitor_interval_seconds", 300))
IDLE_NOTIFY_MINUTES    = int(config.get("crash_monitor_idle_notify_minutes", 15))

# === Runtime files (under utils.RUNTIME_DIR) ===
PID_FILE   = Path(RUNTIME_DIR) / "crash_monitor.pid"
STATE_FILE = Path(RUNTIME_DIR) / "crash_monitor_state.json"
STOP_FLAG  = Path(RUNTIME_DIR) / "stop_crash_monitor.flag"

# === Internals ===
def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass

def _write_state(mode: str) -> None:
    _atomic_write_json(
        STATE_FILE,
        {
            "ts": datetime.utcnow().isoformat() + "Z",
            "mode": mode,
            "pid": os.getpid(),
        },
    )

def _write_pid() -> None:
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass

def _clear_pid_and_stopflag() -> None:
    for p in (PID_FILE, STOP_FLAG):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

def _notify(msg: str) -> None:
    # Channel name is feature/flag gated inside utils
    send_discord_message(msg, channel="crash_monitor")

# === Main ===
def main() -> None:
    if not is_feature_enabled("enable_crash_monitor"):
        print("[CrashMon] Disabled via config; exiting.")
        return

    print("[CrashMon] Starting crash monitor…")
    _notify("🟢 Crash monitor started.")
    _write_pid()
    _write_state("startup")

    last_idle_notice_at: datetime | None = None
    announced_watching = False

    interval = max(5, MONITOR_INTERVAL_SEC)

    while True:
        # 1) graceful stop via flag
        if STOP_FLAG.exists():
            _notify("🛑 Crash monitor stop requested; exiting.")
            _write_state("stopped")
            _clear_pid_and_stopflag()
            return

        # 2) allow live disable via config/features
        if not is_feature_enabled("enable_crash_monitor"):
            _write_state("disabled")
            time.sleep(interval)
            continue

        # 3) suppress during an intentional shutdown sequence
        if is_shutdown_in_progress():
            _write_state("intentional_shutdown")
            time.sleep(interval)
            continue

        # 4) determine server state via shared utils/flags
        flag_present = STATE_FLAG.exists()
        process_running = find_running_server() is not None

        # 4a) No flag -> idle (server not announced as running yet)
        if not flag_present:
            _write_state("idle")
            now = datetime.now()
            if last_idle_notice_at is None:
                _notify("🟡 Crash monitor idle: server flag not present (offline).")
                last_idle_notice_at = now
                announced_watching = False
            elif now - last_idle_notice_at >= timedelta(minutes=IDLE_NOTIFY_MINUTES):
                _notify("🟡 Crash monitor idle (still waiting for server flag)…")
                last_idle_notice_at = now
            time.sleep(interval)
            continue

        # 4b) Flag present + process alive -> watching
        if process_running:
            _write_state("watching")
            if not announced_watching:
                _notify("🧭 Crash monitor active: watching for unexpected exit.")
                announced_watching = True
            time.sleep(interval)
            continue

        # 4c) Crash condition: flag present but process missing
        _write_state("restart_pending")

        # Respect quiet windows (startup / auto-restart suppression)
        if startup_grace_active(180) or autorestart_quiet_active():
            print("[CrashMon] Quiet/startup window active; suppressing restart.")
            time.sleep(interval)
            continue

        # Attempt a controlled restart
        print("[CrashMon] Server process missing unexpectedly (flag present).")
        _notify("❌ Crash monitor detected an unexpected exit. Attempting controlled restart…")

        if initiate_controlled_restart(reason="proc_missing"):
            _notify("🔄 Auto-restart initiated by crash monitor.")
        else:
            _notify("⚠️ Restart already in progress or throttled.")

        # Give the orchestrator a short head start before next check
        time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    finally:
        _clear_pid_and_stopflag()
