"""
crash_monitor.py
Watches for unexpected server exits and triggers a controlled restart.

Behavior improvements:
- Sends a startup message when the monitor begins.
- If server_running.flag is absent (intentional offline), sends an idle notice once,
  then a periodic idle heartbeat (configurable) so you know the monitor is alive.
- When the flag appears (or process is running), announces that it's actively watching.
- If the flag exists but the process is missing, initiates a controlled, throttled restart.
"""

from __future__ import annotations
import time
from datetime import datetime, timedelta
from pathlib import Path

from config_helper import config, is_feature_enabled
from utils import find_running_server, send_discord_message, initiate_controlled_restart, startup_grace_active, autorestart_quiet_active

ROOT_DIR = Path(__file__).resolve().parent
STATE_FLAG = ROOT_DIR / "server_running.flag"

# How frequently the monitor loop runs
MONITOR_INTERVAL = int(config.get("crash_monitor_interval_seconds", 300))

# How often to send an "I'm idle but alive" heartbeat while the flag is absent
IDLE_NOTIFY_MINUTES = int(config.get("crash_monitor_idle_notify_minutes", 15))

def ensure_log_monitor(cfg, base_dir, config_path):
    if not cfg.get("features", {}).get("enable_log_monitor", True):
        return
    show = bool(cfg.get("show_monitor_window", False))
    mon_py = os.path.join(base_dir, "ServerManagment", "Controller", "monitor_log.py")
    spawn_once("Controller\\monitor_log.py",
               [sys.executable, mon_py, "--config", config_path, "--follow"],
               show)

# Wherever you log "[OK] Vein server started..." inside the restart loop:
ensure_log_monitor(CONFIG, BASE_DIR, CONFIG_PATH)

def main() -> None:
    if not is_feature_enabled("enable_crash_monitor"):
        print("[Crash Monitor] Disabled via config; exiting.")
        return
    print("[Crash Monitor] Starting crash monitor...")
    send_discord_message("🟢 Crash monitor started.", channel="crash_monitor")

    last_idle_notice_at: datetime | None = None
    announced_watching = False  # set after we detect flag/process and announce "watching"

    while True:
        # Respect feature toggle dynamically
        if not is_feature_enabled("enable_crash_monitor"):
            time.sleep(MONITOR_INTERVAL)
            continue

        flag_exists = STATE_FLAG.exists()
        proc_running = find_running_server() is not None

        if not flag_exists:
            # Intentional offline: send one "idle" notice, then heartbeat every N minutes
            now = datetime.now()
            if last_idle_notice_at is None:
                send_discord_message("🟡 Crash monitor idle: server flag not present (server likely offline).",
                                     channel="crash_monitor")
                last_idle_notice_at = now
                announced_watching = False  # reset so we re-announce when we start watching again
            else:
                if now - last_idle_notice_at >= timedelta(minutes=IDLE_NOTIFY_MINUTES):
                    send_discord_message("🟡 Crash monitor idle (still): waiting for server flag…",
                                         channel="crash_monitor")
                    last_idle_notice_at = now
            time.sleep(MONITOR_INTERVAL)
            continue

        # Flag exists → we expect the process to be running (server should be up)
        if proc_running:
            if not announced_watching:
                send_discord_message("🧭 Crash monitor active: server running; watching for unexpected exit.",
                                     channel="crash_monitor")
                announced_watching = True
            time.sleep(MONITOR_INTERVAL)
            continue

        # Crash detected: flag exists but the process is missing
        if startup_grace_active(180) or autorestart_quiet_active():
            # During manual boot / quiet window, don't treat this as a crash
            print("[Crash Monitor] Startup/quiet window active; suppressing crash handling.")
            time.sleep(MONITOR_INTERVAL)
            continue

        print("❌ [Crash Monitor] Server process missing unexpectedly (flag present).")
        send_discord_message("❌ Crash monitor detected an unexpected exit. Attempting controlled restart…",
                             channel="crash_monitor")

        if initiate_controlled_restart(reason="proc_missing"):
            send_discord_message("🔄 Auto-restart initiated by crash monitor.", channel="crash_monitor")
        else:
            send_discord_message("⚠️ Restart already in progress or throttled.", channel="crash_monitor")

        # After requesting restart, give it a short head start
        time.sleep(30)

if __name__ == "__main__":
    main()
