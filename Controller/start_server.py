# Controller/start_server.py
from __future__ import annotations
from pathlib import Path
import os, sys, json, time, subprocess

from config_helper import config, is_feature_enabled
from utils import (
    SERVER_DIR, RUNTIME_DIR,
    start_vein_server,
    write_flag, clear_flag,
    stop_log_monitor, stop_crash_monitor,
    create_startup_lock, clear_startup_lock,
    set_autorestart_quiet_period,
    send_discord_message,
    check_for_steam_update,
)

def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass

def _server_state_path() -> Path:
    runtime = Path(config.get("runtime_dir") or (Path(__file__).parents[1] / "Runtime"))
    return runtime / "server_state.json"

def _pyexe() -> str:
    # Honor env_setup.bat; fallback to visible console Python.
    return os.environ.get("PYEXE", "py -3")

from config_helper import config
from utils import win_creationflags_for_headless, headless_enabled
import subprocess
from pathlib import Path

def _spawn_py(script_rel: str):
    try:
        root = Path(__file__).parents[1].resolve()
        script = (root / "Controller" / script_rel).resolve()
        creationflags = win_creationflags_for_headless() if headless_enabled() else 0

        # Management log capture (separate from game logs)
        log_dir = Path(config.get("mgmt_log_dir", root / "Logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout = open(log_dir / f"{script.stem}.stdout.log", "ab", buffering=0)
        stderr = open(log_dir / f"{script.stem}.stderr.log", "ab", buffering=0)

        return subprocess.Popen(
            [_pyexe(), str(script)],
            cwd=str(root),
            creationflags=creationflags,
            stdout=stdout,
            stderr=stderr,
            close_fds=True
        )
    except Exception as e:
        print(f"[Start] Failed to spawn {script_rel}: {e}")
        return None

def _start_monitors() -> None:
    # Clean any stale instances
    stop_log_monitor()
    stop_crash_monitor()
    # Start fresh ones if features enabled
    if bool(config.get("features", {}).get("enable_log_monitor", True)):
        _spawn_py("monitor_log.py")
    if bool(config.get("features", {}).get("enable_crash_monitor", True)):
        _spawn_py("crash_monitor.py")

def _steam_update_if_enabled() -> bool:
    # Gate with features + config(auto_update_on_start)
    feat = bool(config.get("features", {}).get("enable_steam_update", True))
    auto = bool(config.get("auto_update_on_start", True))
    if not feat or not auto:
        return True  # treat as OK (no-op)
    send_discord_message("🧰 Checking Steam version…", channel="startup")
    ok = check_for_steam_update()
    if ok:
        send_discord_message("✅ Steam version up-to-date (or updated).", channel="startup")
    else:
        send_discord_message("⚠️ Steam update failed; continuing with current build.", channel="startup")
    return True  # Don’t hard-fail start if update fails

def main() -> int:
    state_path = _server_state_path()

    # Let monitors know to chill during boot
    create_startup_lock()
    try:
        _atomic_write_json(state_path, {
            "process_running": False,
            "pid": 0,
            "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "exe": None,
            "cwd": str(SERVER_DIR),
        })

        # Startup narration
        send_discord_message("🚀 Vein server preflight starting…", channel="startup")

        # (1) Steam update (optional)
        _steam_update_if_enabled()

        # (2) Start monitors first so they can report "joinable" when log shows it
        _start_monitors()

        # (3) Optional quiet window to suppress crash monitor jitters during boot
        startup_quiet = int(config.get("startup_quiet_seconds", 120))
        if startup_quiet > 0:
            set_autorestart_quiet_period(startup_quiet)

        # (4) Launch server
        proc = start_vein_server()
        if proc is None:
            send_discord_message("❌ Start failed: no executable or launch error.", channel="startup")
            _atomic_write_json(state_path, {
                "process_running": False,
                "pid": 0,
                "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_exit_code": -1,
                "cwd": str(SERVER_DIR),
            })
            return 1

        # (5) Mark running; monitors will take it from here
        _atomic_write_json(state_path, {
            "process_running": True,
            "pid": proc.pid,
            "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_exit_code": None,
            "cwd": str(SERVER_DIR),
        })
        try:
            write_flag(proc.pid, "VeinServer", "")
        except Exception:
            pass

        send_discord_message(f"✅ Server process started (PID {proc.pid}). Waiting for joinable…", channel="startup")
        return 0

    finally:
        # Release quiet/startup lock so crash monitor can behave normally
        clear_startup_lock()

if __name__ == "__main__":
    raise SystemExit(main())
