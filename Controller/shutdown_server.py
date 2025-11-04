"""
shutdown_server.py
Cleanly stops the Vein server and monitors.
"""

# --- EARLY BOOTSTRAP (must run before any local imports) ---------------------
from __future__ import annotations
import os, sys, time, subprocess
from pathlib import Path

# Resolve folders relative to this file
CONTROLLER_DIR = Path(__file__).resolve().parent
MGMT_ROOT      = CONTROLLER_DIR.parent
CONFIG_DIR     = MGMT_ROOT / "Config"

# Send a final Discord warning this many seconds before shutdown (0 = disabled)
COUNTDOWN_FINAL_WARNING_AT = 10

# Ensure module import path
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

# Pick a config.json deterministically (env override wins, else common locations)
candidates = [
    os.environ.get("VEIN_CONFIG"),
    str(CONFIG_DIR / "config.json"),
    str(CONTROLLER_DIR / "config.json"),  # last-resort local drop-in
]
resolved_cfg = None
for c in candidates:
    if c and Path(c).exists():
        resolved_cfg = c
        break

if not resolved_cfg:
    # Make this failure loud and actionable (matches what your .bat echoes)
    msg = "[Shutdown] config.json not found. Looked for:\n  - " + "\n  - ".join([p for p in candidates if p])
    print(msg)
    # Exit non-zero so the .bat shows the error clearly
    raise FileNotFoundError(msg)

# Export for downstream loaders that rely on the environment
os.environ["VEIN_MGMT_ROOT"] = str(MGMT_ROOT)
os.environ["VEIN_CONFIG"]    = resolved_cfg

print(f"[Shutdown] Using VEIN_CONFIG={resolved_cfg}")
# ---------------------------------------------------------------------------

# AFTER this line it's safe to import helpers that read VEIN_CONFIG
from utils import (
    stop_log_monitor, stop_crash_monitor, send_discord_message, backup_save_file,
    SAVE_FILE, clear_flag, stop_all_vein_processes_aggressive,
    list_all_vein_server_procs, set_autorestart_quiet_period,
    begin_intentional_shutdown, end_intentional_shutdown,
    clear_runtime_markers, set_server_state, PID_SERVER,
    is_feature_enabled,
)

# Optional: PRE_SHUTDOWN_WARN knob from config
try:
    from config_helper import config
    PRE_SHUTDOWN_WARN = int(config.get("pre_shutdown_warning_seconds", 0))
except Exception:
    PRE_SHUTDOWN_WARN = 0


def _taskkill_by_name(name: str) -> None:
    try:
        subprocess.run(["taskkill", "/IM", name, "/T", "/F"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _stop_py_process(keyword: str) -> None:
    try:
        import psutil
        for p in psutil.process_iter(attrs=["pid", "cmdline"]):
            cmd = " ".join(p.info.get("cmdline") or [])
            if keyword in cmd:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        _taskkill_by_name("python.exe")


def _clear_locks() -> None:
    # Legacy cleanup for any leftover Controller-local locks/flags
    for fn in ("startup_in_progress.lock", "no_autorestart.until", "server_running.flag"):
        f = CONTROLLER_DIR / fn
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass


def _warn_and_wait(seconds: int) -> None:
    if seconds <= 0:
        return
    # First heads-up to Discord
    try:
        send_discord_message(
            f"⚠️ Intentional shutdown in **{seconds} seconds**. Please finish up.",
            channel="shutdown"
        )
    except Exception:
        pass

    print(f"[Shutdown] Warning window: {seconds}s")
    for remaining in range(seconds, 0, -1):
        # Optional final warning
        if COUNTDOWN_FINAL_WARNING_AT and remaining == COUNTDOWN_FINAL_WARNING_AT:
            try:
                send_discord_message(
                    f"⚠️ Shutdown in **{COUNTDOWN_FINAL_WARNING_AT} seconds**…",
                    channel="shutdown"
                )
            except Exception:
                pass
        time.sleep(1)

def _normal_shutdown() -> None:
    """
    Orderly shutdown triggered by the GUI "Stop Server" button.

    Guarantees:
      - Monitors are stopped first (so they don't misclassify shutdown as a crash).
      - Server processes are terminated (graceful -> forced).
      - All runtime hints are cleared: server_running.flag, server.pid, server_state.json.
      - Optional backup and Discord notification are attempted, but never block shutdown.
    """
    print("[Shutdown] Intentional shutdown requested…")

    # 0) Enter quiet window (prevents auto-restart / crash heuristics)
    begin_intentional_shutdown(window_sec=int(config.get("shutdown_quiet_seconds", 300)))

    # Let Discord know this was operator-initiated
    try:
        send_discord_message("🛑 Intentional shutdown initiated from GUI.", channel="shutdown")
    except Exception:
        pass

    # 1) Immediately clear “server is up” hints so the GUI can't stick green
    try: clear_flag(); PID_SERVER.unlink(missing_ok=True); set_server_state(False, pid=0)
    except Exception: pass

    # 2) Stop monitors first (avoid crash false-positives)
    print("[Shutdown] Stopping monitors…")
    monitors_stopped = True
    try:
        stop_log_monitor()
    except Exception:
        monitors_stopped = False
        _stop_py_process("monitor_log.py")
    try:
        stop_crash_monitor()
    except Exception:
        monitors_stopped = False
        _stop_py_process("crash_monitor.py")

    try:
        if monitors_stopped:
            send_discord_message("📴 Monitors stopped cleanly.", channel="shutdown")
        else:
            send_discord_message("📴 Monitors stop requested (best effort).", channel="shutdown")
    except Exception:
        pass

    # Optional heads-up countdown
    if PRE_SHUTDOWN_WARN:
        _warn_and_wait(PRE_SHUTDOWN_WARN)

    # 3) Stop the server (graceful -> aggressive)
    try:
        running = list_all_vein_server_procs(verbose=True)
    except Exception:
        running = []

    if not running:
        print("[Shutdown] No server process found.")
        try:
            send_discord_message("ℹ️ Shutdown requested, but server was not running.", channel="shutdown")
        except Exception:
            pass
    else:
        pids = [p.pid for p in running]
        print(f"• Stopping server PIDs: {pids}")
        try:
            stop_all_vein_processes_aggressive()
        finally:
            # Belt & suspenders: wipe hints again in case any step recreated/left them
            try: clear_flag()
            except Exception: pass
            try: PID_SERVER.unlink(missing_ok=True)
            except Exception: pass
            try: set_server_state(False, pid=0, last_exit_code=0)
            except Exception: pass

    # 4) Backup + notify (feature-gated and non-blocking)
    zip_path = None
    backup_disabled = False
    try:
        backup_disabled = not is_feature_enabled("enable_backups")
    except Exception:
        # If we can't read config helper, assume enabled and try anyway
        backup_disabled = False

    try:
        if backup_disabled:
            print("[Shutdown] Backups disabled via config; skipping shutdown backup.")
            zip_path = None
        else:
            zip_path = backup_save_file(SAVE_FILE, reason="Shutdown")
    except Exception as e:
        print(f"[Shutdown] Backup failed: {e}")
        zip_path = None

    # Discord notify with specific wording
    try:
        if backup_disabled:
            send_discord_message("🛑 Server shutdown complete. (No backup: backups disabled in config.)", channel="shutdown")
        elif zip_path:
            send_discord_message(f"🛑 Server shutdown complete. Backup created: {zip_path.name}", channel="shutdown")
        else:
            send_discord_message("🛑 Server shutdown complete. (Backup skipped or failed.)", channel="shutdown")
    except Exception:
        pass

def _emergency_shutdown() -> None:
    print("[Shutdown][EMERGENCY] Attempting best-effort stop…")
    _stop_py_process("monitor_log.py")
    _stop_py_process("crash_monitor.py")
    for exe in ("VeinServer-Win64-Shipping.exe", "VeinServer-Win64-Test.exe",
                "VeinServer-Win64-Development.exe", "VeinServer.exe"):
        _taskkill_by_name(exe)
    _clear_locks()
    print("[Shutdown][EMERGENCY] Done. Fix config.json and rerun normally.")

def main() -> None:
    # If config imports worked, run the normal path; else do an emergency stop
    try:
        _ = PRE_SHUTDOWN_WARN  # touch var to ensure the try above succeeded
        _normal_shutdown()
    except Exception:
        _emergency_shutdown()

if __name__ == "__main__":
    main()
