"""
start_server.py
Dynamic entrypoint to start the Vein dedicated server.
Fully portable under the ServerManagment\\Controller folder.
"""

from __future__ import annotations
import os, sys, time, subprocess
from pathlib import Path
import psutil  # pip install psutil

# --- Bootstrap dynamic environment ------------------------------------------
CONTROLLER_DIR = Path(__file__).resolve().parent
MGMT_ROOT = CONTROLLER_DIR.parent
CONFIG_DIR = MGMT_ROOT / "Config"

if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

os.environ.setdefault("VEIN_MGMT_ROOT", str(MGMT_ROOT))
if (CONFIG_DIR / "config.json").exists():
    os.environ.setdefault("VEIN_CONFIG", str(CONFIG_DIR / "config.json"))

# --- Imports (after path setup) ---------------------------------------------
from config_helper import (
    config, is_feature_enabled, is_discord_channel_enabled, get_path
)
from utils import (
    find_running_server, start_vein_server,
    read_flag, write_flag, clear_flag, send_discord_message,
    check_for_steam_update, auto_restore_save_file, rotate_server_log,
    summarize_config, backup_save_file, SAVE_FILE,
    create_startup_lock, clear_startup_lock, set_autorestart_quiet_period,
)

# ---------------------------- Config values ----------------------------
ROOT_DIR = CONTROLLER_DIR
SERVER_DIR = Path(get_path("server_dir"))
EXECUTABLE_NAMES = list(config.get("server_executables", []))
MAP_URL = str(config.get("map_path", "/Game/Vein/Maps/ChamplainValley?listen"))
MAX_PLAYERS = int(config.get("max_players", 8))
MULTI_HOME_IP = str(config.get("multi_home_ip", "0.0.0.0"))

PREBOOT_SHUTDOWN = bool(config.get("preboot_shutdown", True))
BACKUP_ON_DETECT = bool(config.get("backup_on_detect", True))
SHUTDOWN_TIMEOUT = int(config.get("shutdown_timeout_sec", 60))
PRE_SHUTDOWN_WARNING = int(config.get("pre_shutdown_warning_seconds", 0))
STALE_FLAG_DELAY_SEC = int(config.get("stale_flag_delay_sec", 1))


# ---------------------------- Helpers ----------------------------
def _print_preflight_summary() -> None:
    s = summarize_config()
    print("\n=== Vein Server Preflight Summary ===")
    print(f" Server Dir       : {s['server_dir']}")
    print(f" Backup Root      : {s['backup_root']}")
    print(f" Executable (pick): {s['executable_selected'] or 'NOT FOUND'}")
    print(f" Candidates       : {', '.join(s['executable_candidates'])}")
    print(f" Map URL          : {s['map_url']}")
    print(f" Max Players      : {s['max_players']}")
    print(f" Game Port        : {s['game_port']}")
    print(f" Query Port       : {s['query_port']}")
    print(f" MultiHome IP     : {s['multi_home_ip']}")
    print(f" SteamCMD Path    : {s['steamcmd_path'] or '(disabled)'}")
    print(f" App ID           : {s['app_id'] or '(n/a)'}")
    feats = s.get("features", {})
    mlw = int(config.get("monitor_log_wait_timeout_seconds", 60))
    print(" Features         : " + ", ".join(
        f"{k}={'on' if bool(v) else 'off'}" for k, v in feats.items()
    ))
    print(f" Log Wait (boot)  : {mlw}s")
    print("=====================================\n")

    if is_discord_channel_enabled("startup"):
        exe = s["executable_selected"] or "NOT FOUND"
        msg = (
            f"🧭 Preflight: map={s['map_url']} exe={Path(exe).name if exe!='NOT FOUND' else exe} "
            f"port={s['game_port']} ip={s['multi_home_ip']}"
        )
        send_discord_message(msg, channel="startup")

    if s["executable_selected"] is None:
        send_discord_message("❌ No server executable found. Check server_dir & candidates.", channel="startup")
        raise SystemExit(1)


def _graceful_shutdown(proc: psutil.Process, timeout: int = SHUTDOWN_TIMEOUT) -> None:
    try:
        script = CONTROLLER_DIR / "shutdown_server.py"
        if script.exists():
            subprocess.run([sys.executable, str(script)], check=False)
        else:
            proc.terminate()
            proc.wait(timeout=timeout)
    except Exception:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False)
        except Exception:
            pass


def _preflight_guard() -> None:
    """
    Prevent double-starts.
    - If a live server exists:
        * preboot_shutdown=True  -> optional warning, graceful shutdown, restart
        * preboot_shutdown=False -> skip starting (clean exit)
    - If only a stale flag exists: clear quickly (no long waits)
    """
    live_proc = find_running_server(EXECUTABLE_NAMES, SERVER_DIR)
    flag = read_flag()

    if live_proc:
        # Keep the flag in sync with the real PID
        if flag and flag.get("pid") != live_proc.pid:
            write_flag(live_proc.pid, "", MAP_URL)

        if PREBOOT_SHUTDOWN:
            if PRE_SHUTDOWN_WARNING > 0:
                send_discord_message(
                    f"⚠️ Server restart in {PRE_SHUTDOWN_WARNING}s…",
                    channel="startup"
                )
                time.sleep(PRE_SHUTDOWN_WARNING)

            if BACKUP_ON_DETECT:
                backup_save_file(SAVE_FILE, reason="Startup")

            send_discord_message("🔁 Instance running: shutting down for restart…", channel="startup")
            _graceful_shutdown(live_proc, timeout=SHUTDOWN_TIMEOUT)
            clear_flag()
            time.sleep(2)  # small settle before relaunch
            return
        else:
            send_discord_message("⏭️ Start skipped; server already running.", channel="startup")
            raise SystemExit(0)

    # No live process found
    if flag:
        # Stale flag only → clear quickly (no warning, no long wait)
        if BACKUP_ON_DETECT:
            backup_save_file(SAVE_FILE, reason="Startup")
        clear_flag()
        if STALE_FLAG_DELAY_SEC > 0:
            time.sleep(STALE_FLAG_DELAY_SEC)
    # continue to normal startup
    
import os, sys, subprocess

def _creation_flags(show_window: bool) -> int:
    # CREATE_NEW_CONSOLE (0x10) for visible; CREATE_NO_WINDOW (0x08000000) for hidden
    return (0x10 if show_window else 0x08000000)

def spawn_once(tag_substring: str, argv: list[str], show_window: bool):
    """
    Start a process if another with tag_substring isn't already running.
    Uses a light psutil check if available; otherwise best effort.
    """
    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            cmd = " ".join(p.info.get("cmdline") or [])
            if tag_substring in cmd:
                print(f"[Monitors] {tag_substring} already running; skip.")
                return
    except Exception:
        pass

    subprocess.Popen(argv, creationflags=_creation_flags(show_window), close_fds=False)
    print(f"[Monitors] started: {tag_substring}")
    
def maybe_start_monitors(cfg, base_dir, config_path):
    feats = cfg.get("features", {})
    show = bool(cfg.get("show_monitor_window", False))

    # Crash monitor
    if feats.get("enable_crash_monitor", True):
        crash_py = os.path.join(base_dir, "ServerManagment", "Controller", "crash_monitor.py")
        spawn_once("Controller\\crash_monitor.py",
                   [sys.executable, crash_py, "--config", config_path],
                   show)

    # Log monitor (optional to start here — see Section 3)
    if feats.get("enable_log_monitor", True):
        mon_py = os.path.join(base_dir, "ServerManagment", "Controller", "monitor_log.py")
        # pass --follow to behave like 'tail -F'
        spawn_once("Controller\\monitor_log.py",
                   [sys.executable, mon_py, "--config", config_path, "--follow"],
                   show)


# ---------------------------- Main ----------------------------
def main() -> None:
    create_startup_lock()
    set_autorestart_quiet_period(int(config.get("startup_quiet_seconds", 120)))
    try:
        clear_flag()
        _print_preflight_summary()
        _preflight_guard()

        if is_feature_enabled("enable_steam_update"):
            if is_discord_channel_enabled("startup"):
                send_discord_message("🔄 Checking for SteamCMD updates…", channel="startup")
            check_for_steam_update()

        auto_restore_save_file()
        rotate_server_log()

        proc = start_vein_server(
            max_players=MAX_PLAYERS,
            ip=MULTI_HOME_IP,
            server_dir=SERVER_DIR,
            extra_args=None,
        )
        if proc is None:
            send_discord_message("❌ Failed to launch Vein server.", channel="startup")
            raise SystemExit(1)

        print(f"[OK] Vein server started. PID={proc.pid}  Map={MAP_URL}")
        send_discord_message(f"🟢 Server online (PID {proc.pid}).", channel="startup")
    finally:
        clear_startup_lock()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        p = find_running_server(EXECUTABLE_NAMES, SERVER_DIR)
        if p:
            _graceful_shutdown(p, timeout=SHUTDOWN_TIMEOUT)
        clear_flag()
        raise
