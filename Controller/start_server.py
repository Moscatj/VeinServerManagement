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
    RESTARTING_LOCK,
    clear_runtime_markers, stop_all_vein_processes_aggressive, PID_SERVER,
)
from Tools.config_io import load_and_validate_config

# --- Config path resolution (shared by this module & spawned children) ---
def _default_config_path() -> Path:
    # Prefer explicit env first (your BATs set VEIN_CONFIG); otherwise fall back to repo default
    return Path(os.environ.get("VEIN_CONFIG") or (Path(__file__).parents[1] / "Config" / "config.json"))

CONFIG_PATH: Path = _default_config_path()
CONFIG_DIR:  Path = CONFIG_PATH.parent

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

def _clear_restart_lock():
    try:
        RESTARTING_LOCK.unlink(missing_ok=True)
    except Exception:
        pass

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
        env = os.environ.copy()
        # Ensure children see the same config file path
        env.setdefault("VEIN_CONFIG", str(CONFIG_PATH))

        # propagate PYEXE if you’re launching helpers from a BAT later
        env.setdefault("PYEXE", os.environ.get("PYEXE", "py -3"))

        print(f"[Start] Spawning {script_name}: {' '.join(cmd)}  (cwd={_controller_root()})")

        subprocess.Popen(
            cmd,
            cwd=str(_controller_root()),
            env=env,                     # <— add this
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
    # Always begin with a clean slate
    stop_log_monitor()
    stop_crash_monitor()

    # Clear stale flags/PIDs that can block a fresh boot
    try:
        runtime = Path(config.get("runtime_dir") or (Path(__file__).parents[1] / "Runtime"))
        for fn in ("stop_log_monitor.flag", "log_monitor.pid",
                   "stop_crash_monitor.flag", "crash_monitor.pid"):
            try:
                (runtime / fn).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

    feats = dict(config.get("features", {}))
    wanted = []
    started = []

    if feats.get("enable_log_monitor", True):
        wanted.append("log")
        if _spawn_py("monitor_log.py"):
            started.append("log")

    if feats.get("enable_crash_monitor", True):
        wanted.append("crash")
        if _spawn_py("crash_monitor.py"):
            started.append("crash")

    if not wanted:
        send_discord_message("ℹ️ Monitors disabled by config; none requested.", channel="startup")
    elif not started:
        send_discord_message("⚠️ Monitor spawn failed (see mgmt logs).", channel="startup")
    else:
        send_discord_message(f"🟢 Monitors started: {', '.join(started)}", channel="startup")

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
    # 0) Load + validate config once (paths, exe choice, hb knobs)
    from Tools.config_io import load_and_validate_config
    vcfg = load_and_validate_config(CONFIG_PATH)  # CONFIG_PATH should already point to Config/config.json

    SERVER_DIR_PATH: Path = vcfg.server_dir
    RUNTIME_DIR_PATH: Path = vcfg.runtime_dir
    SELECTED_EXE: Path = vcfg.selected_exe
    EXTRA_ARGS = vcfg.raw.get("extra_launch_args", [])

    # --- DEBUG breadcrumb ---
    try:
        from datetime import datetime
        (RUNTIME_DIR / "restart_debug.log").write_text(
            f"{datetime.utcnow().isoformat()}Z  start_server.py entry\n",
            encoding="utf-8"
        )
    except Exception:
        pass
    # -------------------------

    # Paths/pids based on validated runtime dir
    state_path = RUNTIME_DIR_PATH / "server_state.json"
    pid_log    = RUNTIME_DIR_PATH / "log_monitor.pid"
    # If you have a different PID path global, keep it, else derive here:
    pid_server_path = PID_SERVER if 'PID_SERVER' in globals() else (RUNTIME_DIR_PATH / "server.pid")

    # 1) Let monitors know to chill during boot
    create_startup_lock()
    try:
        _atomic_write_json(state_path, {
            "process_running": False,
            "pid": 0,
            "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "exe": None,
            "cwd": str(SERVER_DIR_PATH),
            "headless": current_headless_flag(),
        })

        # 2) Startup narration
        send_discord_message("🚀 Vein server preflight starting…", channel="startup")

        # 3) Steam check/update (optional)
        _steam_update_if_enabled()

        # 4) Start monitors BEFORE launching server so log monitor watches whole boot
        _start_monitors()

        # Verify log monitor actually started; if not, re-spawn once
        try:
            time.sleep(1.5)  # small settle
            if not pid_log.exists():
                _spawn_py("monitor_log.py")  # fire one more time
                time.sleep(1.0)
        except Exception:
            pass

        # 5) Optional quiet window to suppress crash monitor jitters during boot
        #    (prefer the new monitor.* home if you added it; fall back to legacy key)
        startup_quiet = int(
            (vcfg.raw.get("monitor", {}) or {}).get("startup_quiet_seconds",
                vcfg.raw.get("startup_quiet_seconds", 120))
        )
        if startup_quiet > 0:
            set_autorestart_quiet_period(startup_quiet)

        # 6) Launch server (prefer explicit exe + cwd).
        try:
            # Debug: show which exe we’re about to launch
            send_discord_message(f"🧩 Selected exe: {SELECTED_EXE}", channel="startup")

            # Preflight: verify the exe actually exists
            if not SELECTED_EXE.exists():
                # Try to locate an alternative
                found = []
                for name in vcfg.server_executables:
                    cand = vcfg.server_dir / name
                    if cand.exists():
                        found.append(str(cand))
                # Report what we found
                send_discord_message(
                    "❌ Selected exe not found.\n"
                    f"• Tried: {SELECTED_EXE}\n"
                    f"• server_dir: {vcfg.server_dir}\n"
                    f"• Found alternatives: {found or 'none'}",
                    channel="startup"
                )
                # If there is a match, switch to first found
                if found:
                    SELECTED_EXE = Path(found[0])
                    send_discord_message(f"🔄 Falling back to {SELECTED_EXE}", channel="startup")

            # Attempt to launch
            proc = start_vein_server(
                executable=str(SELECTED_EXE),
                cwd=str(SERVER_DIR_PATH),
                extra_args=list(map(str, EXTRA_ARGS))
            )

        except TypeError:
            # Fallback: legacy signature compatibility
            os.environ["VEIN_SELECTED_EXE"] = str(SELECTED_EXE)
            os.environ["VEIN_SERVER_CWD"] = str(SERVER_DIR_PATH)
            os.environ["VEIN_EXTRA_ARGS"] = " ".join(map(str, EXTRA_ARGS))
            proc = start_vein_server()

        if proc is None:
            send_discord_message("❌ Start failed: no executable or launch error.", channel="startup")
            _atomic_write_json(state_path, {
                "process_running": False,
                "pid": 0,
                "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "last_exit_code": -1,
                "cwd": str(SERVER_DIR_PATH),
                "headless": current_headless_flag(),
            })
            _clear_restart_lock()
            return 1

        # 7) Mark running; monitors (log) will later report “joinable”
        _atomic_write_json(state_path, {
            "process_running": True,
            "pid": proc.pid,
            "last_start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "last_exit_code": None,
            "cwd": str(SERVER_DIR_PATH),
        })
        try:
            pid_server_path.write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass

        _clear_restart_lock()
        send_discord_message(f"✅ Server process started (PID {proc.pid}). Waiting for joinable…", channel="startup")

        return 0

    finally:
        # Release startup lock so crash monitor behaves normally post-boot
        clear_startup_lock()
        _clear_restart_lock()


if __name__ == "__main__":
    raise SystemExit(main())
