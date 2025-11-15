"""
shutdown_server.py
Cleanly stops the Vein server and monitors.
"""

from __future__ import annotations
import os, sys, time, subprocess
from pathlib import Path

CONTROLLER_DIR = Path(__file__).resolve().parent
MGMT_ROOT      = CONTROLLER_DIR.parent
CONFIG_DIR     = MGMT_ROOT / "Config"

# Send a final Discord warning this many seconds before shutdown (0 = disable)
COUNTDOWN_FINAL_WARNING_AT = 10

print(f"[ShutdownScript] argv={sys.argv} parent_pid={os.getppid()}")

# Ensure module import path
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

# Make sure the config loader knows where the management root is.
# config.load_config() will then look for:
#   - VEIN_CONFIG (if set externally)
#   - Config/config.yaml
#   - Config/config.yml
#   - Config/config.json
#   - Controller/config.json
os.environ["VEIN_MGMT_ROOT"] = str(MGMT_ROOT)
print(f"[Shutdown] Using VEIN_MGMT_ROOT={MGMT_ROOT}")

# Safe to import helpers after VEIN_MGMT_ROOT is set
from utils import (
    stop_log_monitor, stop_crash_monitor, send_discord_message, backup_save_file,
    SAVE_FILE, clear_flag, stop_all_vein_processes_aggressive,
    list_all_vein_server_procs, begin_intentional_shutdown, end_intentional_shutdown,
    clear_runtime_markers, set_server_state, PID_SERVER, is_feature_enabled,
)

from config_helper import config

try:
    PRE_SHUTDOWN_WARN = int(config.get("pre_shutdown_warning_seconds", 0))
except Exception:
    PRE_SHUTDOWN_WARN = 0

try:
    # Use shutdown_final_warning_at if present (mapped from lifecycle.shutdown.final_warning_at)
    COUNTDOWN_FINAL_WARNING_AT = int(
        config.get("shutdown_final_warning_at", COUNTDOWN_FINAL_WARNING_AT)
    )
except Exception:
    # Keep the existing default (10) on any error
    pass

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
    for fn in ("startup_in_progress.lock", "no_autorestart.until", "server_running.flag"):
        try:
            (CONTROLLER_DIR / fn).unlink(missing_ok=True)
        except Exception:
            pass


def _warn_and_wait(seconds: int) -> None:
    if seconds <= 0:
        return
    try:
        send_discord_message(
            f"⚠️ Intentional shutdown in **{seconds} seconds**. Please finish up.",
            channel="shutdown"
        )
    except Exception:
        pass
    print(f"[Shutdown] Warning window: {seconds}s")
    for remaining in range(seconds, 0, -1):
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
    print("[Shutdown] Intentional shutdown requested…")

    # 0) Quiet window to suppress auto-restart/crash heuristics
    begin_intentional_shutdown(window_sec=int(config.get("shutdown_quiet_seconds", 300)))

    # 0.1) Announce operator-initiated shutdown
    try:
        send_discord_message("🛑 Intentional shutdown initiated from GUI.", channel="shutdown")
    except Exception:
        pass

    # 1) Clear “server up” hints early so GUI won't stick green
    try:
        clear_flag()
        PID_SERVER.unlink(missing_ok=True)
        set_server_state(False, pid=0)
    except Exception:
        pass

    # 2) Stop monitors first
    try:
        rt = Path(os.environ.get("VEIN_CONFIG") or "").resolve().parent.parent / "Runtime"
    except Exception:
        rt = CONTROLLER_DIR.parent / "Runtime"
    for fn in ("stop_log_monitor.flag","log_monitor.pid","stop_crash_monitor.flag","crash_monitor.pid"):
        try: (rt / fn).unlink(missing_ok=True)
        except Exception: pass
        
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
        send_discord_message(
            "📴 Monitors stopped cleanly." if monitors_stopped else "📴 Monitors stop requested (best effort).",
            channel="shutdown"
        )
    except Exception:
        pass

    # 3) Pre-shutdown countdown (optional)
    if PRE_SHUTDOWN_WARN:
        _warn_and_wait(PRE_SHUTDOWN_WARN)

    # 4) Stop the server unconditionally (race-proof) and re-clear hints
    try:
        snapshot = [p.pid for p in list_all_vein_server_procs(verbose=True)]
        if snapshot:
            print(f"[Shutdown] Observed server PIDs before stop: {snapshot}")
    except Exception:
        pass

    try:
        stop_all_vein_processes_aggressive()
    finally:
        try:
            clear_flag()
        except Exception:
            pass
        try:
            PID_SERVER.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            set_server_state(False, pid=0, last_exit_code=0)
        except Exception:
            pass

    # 5) Backup (feature-gated) + final Discord
    zip_path = None
    backup_disabled = False
    try:
        backup_disabled = not is_feature_enabled("enable_backups")
    except Exception:
        backup_disabled = False

    try:
        if backup_disabled:
            print("[Shutdown] Backups disabled via config; skipping shutdown backup.")
        else:
            zip_path = backup_save_file(SAVE_FILE, reason="Shutdown")
    except Exception as e:
        print(f"[Shutdown] Backup failed: {e}")
        zip_path = None

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
    try:
        _ = PRE_SHUTDOWN_WARN
        _normal_shutdown()
    finally:
        # Always clear locks & quiet window at the end
        try: _clear_locks()
        except Exception: pass
        try: end_intentional_shutdown()
        except Exception: pass
        print("[Shutdown] complete.")


if __name__ == "__main__":
    main()
