# Controller/start_server.py
from __future__ import annotations
from pathlib import Path
import os, sys, json, time, subprocess, shlex

from config_helper import config, is_feature_enabled
from utils import (
    SERVER_DIR,
    start_vein_server,
    write_flag,
    stop_log_monitor, stop_crash_monitor,
    create_startup_lock, clear_startup_lock,
    set_autorestart_quiet_period,
    send_discord_message,
    check_for_steam_update,
    win_creationflags_for_headless, headless_enabled,
    current_headless_flag,
)

# --------- small io helpers ---------
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

def _py_argv() -> list[str]:
    """
    Return the Python launcher command as a list of args.
    Handles env 'PYEXE' like 'py -3' by splitting it safely.
    """
    s = os.environ.get("PYEXE", "py -3").strip()
    # On Windows, shlex.split(..., posix=False) preserves quoting semantics.
    return shlex.split(s, posix=(os.name != "nt"))

def _controller_root() -> Path:
    return Path(__file__).parents[1].resolve()

def _controller_path(name: str) -> Path:
    return _controller_root() / "Controller" / name

def _spawn_py(script_name: str) -> bool:
    """
    Start a Python helper (monitor_log.py / crash_monitor.py) headlessly with
    stdout/stderr captured into mgmt_log_dir so the GUI can tail them.
    Posts a Discord warning on failure with useful context.
    """
    try:
        script = _controller_path(script_name)
        if not script.exists():
            msg = f"[Start] Script not found: {script}"
            print(msg)
            send_discord_message(f"⚠️ {msg}", channel="startup")
            return False

        creationflags = win_creationflags_for_headless() if headless_enabled() else 0

        log_dir = Path(config.get("mgmt_log_dir", _controller_root() / "Logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout = open(log_dir / f"{script.stem}.stdout.log", "ab", buffering=0)
        stderr = open(log_dir / f"{script.stem}.stderr.log", "ab", buffering=0)

        cmd = _py_argv() + [str(script)]
        # For visibility in the mgmt log:
        print(f"[Start] Spawning {script_name}: {' '.join(cmd)}  (cwd={_controller_root()})")

        subprocess.Popen(
            cmd,
            cwd=str(_controller_root()),
            creationflags=creationflags,
            stdout=stdout, stderr=stderr,
            close_fds=True
        )
        return True
    except Exception as e:
        msg = f"[Start] Failed to spawn {script_name}: {e}"
        print(msg)
        send_discord_message(f"⚠️ {msg}", channel="startup")
        return False

def _start_monitors() -> None:
    # Best-effort cleanup: kill any lingering instances
    stop_log_monitor()
    stop_crash_monitor()

    feats = dict(config.get("features", {}))
    started = []

    if feats.get("enable_log_monitor", True):
        if _spawn_py("monitor_log.py"):
            started.append("log")

    if feats.get("enable_crash_monitor", True):
        if _spawn_py("crash_monitor.py"):
            started.append("crash")

    if started:
        send_discord_message(f"🟢 Monitors started: {', '.join(started)}", channel="startup")
    else:
        send_discord_message("⚠️ No monitors started (disabled or spawn failed).", channel="startup")

def _steam_update_if_enabled() -> None:
    """Narrate Steam update; never hard-fail start if update fails."""
    feat = bool(config.get("features", {}).get("enable_steam_update", True))
    auto = bool(config.get("auto_update_on_start", True))
    if not feat or not auto:
        return
    send_discord_message("🧰 Checking Steam version…", channel="startup")
    ok = check_for_steam_update()
    if ok:
        send_discord_message("✅ Steam version up-to-date (or updated).", channel="startup")
    else:
        send_discord_message("⚠️ Steam update failed; continuing with current build.", channel="startup")

# --------- main orchestrator ---------
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
            "headless": current_headless_flag(),
        })

        # Startup narration
        send_discord_message("🚀 Vein server preflight starting…", channel="startup")

        # (1) Steam check/update (optional)
        _steam_update_if_enabled()

        # (2) Start monitors BEFORE launching server so log monitor can watch the whole boot
        _start_monitors()

        # (3) Optional quiet window to suppress crash monitor jitters during boot
        startup_quiet = int(config.get("startup_quiet_seconds", 120))
        if startup_quiet > 0:
            set_autorestart_quiet_period(startup_quiet)

        # (4) Launch server (utils handles headless/visible & flag write)
        proc = start_vein_server()
        if proc is None:
            send_discord_message("❌ Start failed: no executable or launch error.", channel="startup")
            _atomic_write_json(state_path, {
                "process_running": False,
                "pid": 0,
                "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_exit_code": -1,
                "cwd": str(SERVER_DIR),
                "headless": current_headless_flag(),
            })
            return 1

        # (5) Mark running; monitors (log) will later report “joinable”
        _atomic_write_json(state_path, {
            "process_running": True,
            "pid": proc.pid,
            "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_exit_code": None,
            "cwd": str(SERVER_DIR),
        })

        # utils.start_vein_server() already wrote the runtime flag; the extra call is harmless,
        # but we can skip it to avoid duplication:
        # write_flag(proc.pid, "VeinServer", "")

        send_discord_message(f"✅ Server process started (PID {proc.pid}). Waiting for joinable…", channel="startup")
        return 0

    finally:
        # Release startup lock so crash monitor behaves normally post-boot
        clear_startup_lock()

if __name__ == "__main__":
    raise SystemExit(main())
