# utils.py
"""
Shared helpers for the Vein dedicated server toolkit.

Responsibilities:
- Process discovery and lifecycle (find/stop/start)
- Flag management (server_running.flag JSON)
- Backups (on-demand, autosave-triggered, nightly), restore, pruning
- SteamCMD update
- Discord notifications (feature- and channel-gated)
- Log rotation (optional, disabled by default via config)
- Crash-safe controlled restarts (startup lock + quiet window)
- Config preflight summary helpers

All paths, ports, and feature toggles come from config.json via config_helper.
No hardcoded paths. Minimal CPU/IO: sleeps and retries are conservative.
"""

from __future__ import annotations

import os
import sys
import json
import time
import zipfile
import shutil
import subprocess
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from Tools.discord import send_discord_message, is_discord_channel_enabled
from Tools.state_io import write_state as _write_server_state, default_state as _default_server_state
from config_helper import (
    config,
    is_feature_enabled,
    is_discord_channel_enabled,
    get_path,
    # NEW (for config summary only; not required for the shims)
    backups_cfg,
)


import psutil  # pip install psutil
#from Controller.utils import process, config_io, log_events, discord, backups

from config_helper import (
    config,
    is_feature_enabled,
    is_discord_channel_enabled,
    get_path,
)

# ----------------------------
# Resolved config & constants
# ----------------------------

PROJECT_ROOT   = Path(__file__).resolve().parents[1] 
CONTROLLER_DIR = PROJECT_ROOT / "Controller"
SERVER_DIR: Path = Path(get_path("server_dir"))
BACKUP_ROOT: Path = Path(get_path("backup_root"))
START_SCRIPT   = (CONTROLLER_DIR / "start_server.py").resolve()

#all ephemeral state goes under runtime_dir
RUNTIME_DIR: Path = Path(get_path("runtime_dir") or (PROJECT_ROOT / "Runtime"))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# Coordination files
STARTUP_LOCK = RUNTIME_DIR / "startup_in_progress.lock"
QUIET_UNTIL  = RUNTIME_DIR / "no_autorestart.until"
RESTARTING_LOCK: Path = RUNTIME_DIR / "restarting.lock"
RESTART_STAMP: Path  = RUNTIME_DIR / "last_restart_at.txt"

# State flag (authoritative “server is running” record) → in Runtime
STATE_FLAG: Path = RUNTIME_DIR / "server_running.flag"

# Runtime file
PID_SERVER: Path   = RUNTIME_DIR / "server.pid"
SERVER_STATE: Path = RUNTIME_DIR / "server_state.json"

# New: explicit “we are intentionally shutting down” marker
SHUTDOWN_FLAG: Path = RUNTIME_DIR / "shutdown_in_progress.flag"

# Executable candidates
EXECUTABLE_NAMES: List[str] = list(config.get("server_executables", []))

# Launch settings
MAP_URL: str      = str(config.get("map_path", "/Game/Vein/Maps/ChamplainValley?listen"))
MAX_PLAYERS: int  = int(config.get("max_players", 8))
GAME_PORT: int    = int(config.get("game_port", 7777))
QUERY_PORT: int   = int(config.get("query_port", 27015))
MULTI_HOME_IP: str = str(config.get("multi_home_ip", "0.0.0.0"))

# Optional explicit log file
ABSOLUTE_LOG_FILE: str = str(config.get("absolute_log_file", "") or "")

# Server output mode
headless = bool(config.get("headless_mode", False))

# Steam update
STEAMCMD_PATH: str = str(config.get("steamcmd_path", "") or "")
APP_ID: str        = str(config.get("app_id", "") or "")

# Backups retention (global defaults; feature-gated at call site)
MAX_BACKUPS: int          = int(config.get("max_backups", 10))
BACKUP_MAX_AGE_DAYS: int  = int(config.get("backup_max_age_days", 7))

_raw_bf = config.get("backup_folders", {})
if isinstance(_raw_bf, dict):
    BACKUP_FOLDERS: Dict[str, str] = _raw_bf
elif isinstance(_raw_bf, str) and _raw_bf.strip():
    # allow a single base path; derive subfolders
    base = _raw_bf.rstrip("/\\")
    BACKUP_FOLDERS = {
        "Manual":   f"{base}/Manual",
        "Startup":  f"{base}/Startup",
        "Autosave": f"{base}/Autosave",
        "Crash":    f"{base}/Crash",
    }
else:
    BACKUP_FOLDERS = {}

# Save & Logs (config-driven)
SAVE_DIR: Path = Path(config.get("save_dir") or (SERVER_DIR / "Vein" / "Saved"))
SAVE_FILENAMES: List[str] = list(config.get("save_filenames", ["Server.vns", "Server.sav"]))
LOGS_DIR: Path = Path(config.get("logs_dir") or (SERVER_DIR / "Vein" / "Saved" / "Logs"))

# Log rotation retry knobs (kept lightweight and disabled by default)
LOG_ROTATION_RETRIES = int(config.get("log_rotation_retries", 3))
LOG_ROTATION_RETRY_SLEEP_SECONDS = float(config.get("log_rotation_retry_sleep_seconds", 1.0))

# Image name patterns we consider a Vein server (covers Shipping/Test/Dev variants)
VEIN_IMAGE_PATTERNS = [
    "VeinServer.exe",
    "VeinServer-Win64-Test.exe",
    "VeinServer-*.exe",
]
# Exact image names we pass to taskkill /IM during aggressive cleanup
VEIN_IMAGE_NAMES = [
    "VeinServer.exe",
    "VeinServer-Win64-Test.exe",
    "VeinServer-Win64-Shipping.exe",
    "VeinServer-Win64-Development.exe",
]

# UE helper processes worth killing on shutdown if configured
UE_HELPERS = [
    "CrashReportClient.exe",
    "UnrealCEFSubProcess.exe",
]

# Match an exe/name against a list of patterns (supports wildcards like VeinServer-*.exe)
def _exe_matches_any(name: str | None, patterns: list[str]) -> bool:
    if not name:
        return False
    name = name.strip()
    for pat in patterns:
        try:
            if fnmatch.fnmatch(name, pat):
                return True
        except Exception:
            # be defensive; ignore a bad pattern
            pass
    return False

def _resolve_save_file() -> Path:
    """Pick the first existing save; else return the first configured filename path."""
    for name in SAVE_FILENAMES:
        p = SAVE_DIR / name
        if p.exists():
            return p
    return SAVE_DIR / SAVE_FILENAMES[0]

SAVE_FILE: Path = _resolve_save_file()

# ----------------------------
# Small internals
# ----------------------------
def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _choose_executable(server_dir: Path, names: List[str]) -> Optional[Path]:
    for name in names:
        cand = server_dir / name
        if cand.exists():
            return cand
    return None

def _now() -> float:
    return time.time()
    
# ----------------------------
# log helpers
# ----------------------------
def _console_print(msg: str) -> None:
    """Print without ever crashing on Windows cp1252 consoles."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Strip characters the active console can't encode
        try:
            print(msg.encode("ascii", "ignore").decode("ascii"))
        except Exception:
            # Last resort: print *something*
            print("[log] <unprintable message>")

def log_info(msg: str) -> None:
    _console_print(f"[INFO {datetime.now().strftime('%H:%M:%S')}] {msg}")

def log_warn(msg: str) -> None:
    _console_print(f"[WARN {datetime.now().strftime('%H:%M:%S')}] {msg}")

def log_error(msg: str) -> None:
    _console_print(f"[ERROR {datetime.now().strftime('%H:%M:%S')}] {msg}")

# Optional: try to force UTF-8 for friendlier output, but still keep ASCII safety above.
def try_enable_utf8_stdout() -> None:
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Py3.7+
    except Exception:
        pass

# ----------------------------
# Flag management
# ----------------------------
def write_flag(pid: int, exe: str, map_url: str) -> None:
    data = {"pid": pid, "exe": exe, "map": map_url, "started_at": datetime.utcnow().isoformat()}
    try:
        STATE_FLAG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Flag] Failed to write flag: {e}")

def read_flag() -> Dict[str, Any] | None:
    if not STATE_FLAG.exists():
        return None
    try:
        return json.loads(STATE_FLAG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Flag] Failed to read flag: {e}")
        return None

def clear_flag() -> None:
    try:
        STATE_FLAG.unlink(missing_ok=True)
    except Exception as e:
        print(f"[Flag] Failed to clear flag: {e}")
        
def begin_intentional_shutdown(window_sec: int = 180) -> None:
    """Mark an intentional shutdown and open a quiet window to suppress restarts."""
    try:
        SHUTDOWN_FLAG.write_text(str(int(_now())), encoding="utf-8")
    except Exception:
        pass
    set_autorestart_quiet_period(max(0, window_sec))

def end_intentional_shutdown() -> None:
    """Clear the intentional shutdown marker."""
    try:
        SHUTDOWN_FLAG.unlink(missing_ok=True)
    except Exception:
        pass

def is_shutdown_in_progress(max_age_seconds: int = 900) -> bool:
    """True if shutdown flag exists and is fresh (default ≤15 min)."""
    try:
        if not SHUTDOWN_FLAG.exists():
            return False
        age = _now() - SHUTDOWN_FLAG.stat().st_mtime
        return age <= max_age_seconds
    except Exception:
        return False
        
def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass

def set_server_state(process_running: bool, pid: int = 0, **extra) -> None:
    """
    Unified writer for Runtime/server_state.json.

    Uses Tools.state_io so server_state.json has:
      - schema/version
      - status ("running"/"stopped")
      - pid
      - last_updated (UTC ISO)
      - optional extra fields (last_start_utc, exe, cwd, last_exit_code, etc.)

    If anything goes wrong, we fall back to the legacy minimal format so we
    never completely lose state. Extras are sanitized to avoid json issues.
    """
    status = "running" if process_running else "stopped"

    # 1) Sanitize extras so json can always handle them
    safe_extra: dict[str, Any] = {}
    for k, v in extra.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            safe_extra[k] = v
        else:
            # Paths, datetimes, custom objects, etc → stringify
            safe_extra[k] = str(v)

    try:
        # 2) Base state from state_io
        state = _default_server_state(
            status=status,
            pid=int(pid),
            headless=current_headless_flag(),  # uses config['headless_mode']
            version="utils.set_server_state",
        )

        # 3) Merge sanitized extras
        if safe_extra:
            state.update(safe_extra)

        _write_server_state(SERVER_STATE, state)
    except Exception:
        # Fallback: legacy minimal schema (keeps older tools from exploding)
        try:
            data = {"process_running": bool(process_running), "pid": int(pid), **safe_extra}
            _atomic_write_json(SERVER_STATE, data)
        except Exception:
            # Last resort: swallow so we don't crash callers
            pass

def clear_pid_file() -> None:
    try: PID_SERVER.unlink(missing_ok=True)
    except Exception: pass

def clear_runtime_markers() -> None:
    # one place to clean all “server is up” hints
    clear_flag()
    clear_pid_file()
    try: SERVER_STATE.unlink(missing_ok=True)
    except Exception: pass

# ----------------------------
# Process discovery & lifecycle
# ----------------------------
def find_running_server(
    executable_names: Optional[List[str]] = None,
    server_dir: Optional[Path] = None,
) -> Optional[psutil.Process]:
    names = executable_names or EXECUTABLE_NAMES
    sdir = str((server_dir or SERVER_DIR).resolve())

    # Pass 1: exact name + matching cwd (best case)
    for p in psutil.process_iter(attrs=["pid", "name", "exe", "cwd"]):
        try:
            pname = (p.info.get("name") or "")
            pexe  = os.path.basename(p.info.get("exe") or "")
            pcwd  = p.info.get("cwd") or ""
            if (pname in names or pexe in names) and pcwd and os.path.abspath(pcwd) == sdir:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Pass 2: exact name only (cwd might be empty/inaccessible)
    for p in psutil.process_iter(attrs=["pid", "name", "exe"]):
        try:
            pname = (p.info.get("name") or "")
            pexe  = os.path.basename(p.info.get("exe") or "")
            if pname in names or pexe in names:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Pass 3: wildcard image patterns (Shipping/Dev variants)
    for p in psutil.process_iter(attrs=["pid", "name", "exe"]):
        if _is_vein_server_process(p):
            return p

    return None

def stop_vein_server(timeout: int | None = None) -> bool:
    proc = find_running_server()
    if not proc:
        clear_runtime_markers()   # NEW
        return True
    try:
        send_discord_message("🛑 stop_vein_server(): requesting graceful shutdown of server process.", channel="startup")
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout or int(config.get("shutdown_timeout_sec", 60)))
        clear_runtime_markers()   # NEW
        set_server_state(False, pid=0, last_exit_code=0)  # NEW
        return True
    except Exception:
        pass
    # force-kill fallback
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clear_runtime_markers()   # NEW
        set_server_state(False, pid=0, last_exit_code=-1) # NEW
        return True
    except Exception:
        return False

def _is_vein_server_process(p: psutil.Process) -> bool:
    """True if this process looks like a Vein dedicated server, even when cwd is missing."""
    try:
        name = (p.info.get("name") or "")
        exe  = os.path.basename(p.info.get("exe") or "")
        return _exe_matches_any(name, VEIN_IMAGE_PATTERNS) or _exe_matches_any(exe, VEIN_IMAGE_PATTERNS)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def list_all_vein_server_procs(verbose: bool = False) -> list[psutil.Process]:
    """Return ALL Vein server processes regardless of cwd (handles background processes)."""
    procs: list[psutil.Process] = []
    for p in psutil.process_iter(attrs=["pid", "name", "exe", "cmdline"]):
        try:
            if _is_vein_server_process(p):
                if verbose:
                    try:
                        print(f"[Find] PID={p.pid} name={p.info.get('name')} exe={p.info.get('exe')}")
                    except Exception:
                        pass
                procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs

def kill_process_tree(pid: int, timeout: int = 5) -> None:
    """Terminate a process and its children; force kill if needed."""
    try:
        parent = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return
    procs = [parent] + parent.children(recursive=True)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    psutil.wait_procs(procs, timeout=timeout)
    for p in procs:
        try:
            if p.is_running():
                p.kill()
        except Exception:
            pass

def stop_all_vein_processes_aggressive() -> list[int]:
    """
    Stop ALL Vein server processes (any variant) and their child trees.
    Returns list of PIDs we acted upon.
    """
    acted: list[int] = []
    procs = list_all_vein_server_procs(verbose=True)
    if not procs:
        return acted
    timeout = int(config.get("shutdown_timeout_sec", 60))

    send_discord_message("🛑 stop_all_vein_processes_aggressive(): killing all VeinServer processes.", channel="startup")

    # Phase 1: psutil tree terminate/kill
    for p in procs:
        try:
            acted.append(p.pid)
            kill_process_tree(p.pid, timeout=timeout)
        except Exception:
            try:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    # Phase 2: image-name sweep (handles orphans)
    for img in VEIN_IMAGE_NAMES:
        try:
            subprocess.run(["taskkill", "/IM", img, "/T", "/F"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # Phase 3: UE helper spillovers (optional)
    if bool(config.get("kill_ue_helpers_on_shutdown", True)):
        for img in UE_HELPERS:
            try:
                subprocess.run(["taskkill", "/IM", img, "/T", "/F"], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    # Phase 4: Exact ExecutablePath kill via PowerShell/WMI (belt & suspenders)
    leftovers = list_all_vein_server_procs(verbose=True)
    if leftovers:
        exe_paths = []
        seen = set()
        for p in leftovers:
            try:
                path = p.info.get("exe") or p.exe()
                if path and path not in seen:
                    seen.add(path)
                    exe_paths.append(path)
            except Exception:
                continue
        _powershell_kill_by_fullpaths(exe_paths)

    # Ensure runtime state is cleared after aggressive stop
    try:
        clear_runtime_markers()
        set_server_state(False, pid=0, last_exit_code=-1)
    except Exception:
        pass


    return sorted(set(acted))
    
def stop_all_monitors() -> None:
    """Stops both monitors and clears their flags safely."""
    stop_log_monitor()
    stop_crash_monitor()

def _powershell_kill_by_fullpaths(paths: list[str]) -> None:
    """Kill processes by exact ExecutablePath using WMI/PowerShell."""
    if not paths:
        return
    lines = []
    for p in paths:
        q = p.replace("\\", "\\\\")
        lines.append(
            f"$p = Get-CimInstance Win32_Process -Filter \"ExecutablePath='{q}'\";"
            f"if ($p) {{ $p | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }} }}"
        )
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "; ".join(lines)],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ----------------------------
# Launching
# ----------------------------
EXTRA_LAUNCH_ARGS: List[str] = list(config.get("extra_launch_args", []))
ENABLE_QUERY_PORT: bool = bool(config.get("enable_query_port", True))

def start_vein_server(
    max_players: int = MAX_PLAYERS,
    ip: str = MULTI_HOME_IP,
    server_dir: Path = SERVER_DIR,
    extra_args: Optional[List[str]] = None,
    *,
    executable: Optional[str] = None,   # (optional) fully-qualified path to exe
    cwd: Optional[str | Path] = None    # (optional) working directory
) -> Optional[subprocess.Popen]:
    """
    Launch the Vein server.

    Behavior (unchanged):
      - When config['headless_mode'] == True:
          * Do NOT pass -log (prevents UE console window)
          * Spawn with CREATE_NO_WINDOW | DETACHED_PROCESS and stdio -> NUL
          * If the process exits immediately, fall back once to visible mode
      - When False:
          * Ensure -log is present (visible console for debugging)

    New:
      - If 'executable' is provided, use it directly (no reselect).
      - If 'cwd' is provided, use it as working dir; else use 'server_dir'.
      - 'extra_args' here are merged with config EXTRA_LAUNCH_ARGS (call-site can override).
    """
    # -------- Resolve exe and CWD (new behavior, non-breaking) --------
    if executable:
        exe = Path(executable).expanduser()
    else:
        exe = _choose_executable(server_dir, EXECUTABLE_NAMES)
        if not exe:
            print("[Start] No server executable found in candidates.")
            return None

    workdir = Path(cwd).expanduser() if cwd is not None else Path(server_dir)

    headless = bool(config.get("headless_mode", False))
    enable_query_port = bool(config.get("enable_query_port", True))
    abs_log_file = str(config.get("absolute_log_file", "") or "")

    # Helper to merge args without dupes (last-write-wins for flags that appear once)
    def _merged_launch_args(extra_from_call: Optional[List[str]]) -> List[str]:
        base = list(EXTRA_LAUNCH_ARGS or [])
        tail = list(extra_from_call or [])
        if not base:
            return tail
        if not tail:
            return base
        # simple merge preferring call-site duplicates (keep order)
        merged = list(base)
        for a in tail:
            try:
                i = merged.index(a)
                merged[i] = a
            except ValueError:
                merged.append(a)
        return merged

    def build_args(visible_console: bool) -> List[str]:
        args: List[str] = [str(exe)]

        # Map/URL
        map_url = (MAP_URL or "").strip()
        if map_url:
            args.append(map_url)

        # Dedicated server flag
        if "-server" not in args:
            args.append("-server")

        # Capacity / network binding
        if max_players and int(max_players) > 0:
            args.append(f"-MaxPlayers={int(max_players)}")
        if ip and ip != "0.0.0.0":
            args.append(f"-MultiHome={ip}")

        # Ports
        if GAME_PORT:
            args.append(f"-port={int(GAME_PORT)}")
        if enable_query_port and QUERY_PORT:
            args.append(f"-QueryPort={int(QUERY_PORT)}")

        # Logging path for GUI tailing
        if abs_log_file:
            args.append(f"-Abslog={abs_log_file}")

        # Output / console behavior
        if visible_console:
            if "-log" not in args:
                args.append("-log")  # force UE console window in visible mode
        else:
            # Ensure -log is not present in headless
            try:
                while True:
                    args.remove("-log")
            except ValueError:
                pass

        # Stability flags
        args.extend(["-Unattended", "-NoCrashDialog"])

        # Additional args from config/caller (call-site overrides duplicates)
        args.extend(_merged_launch_args(extra_args))

        return args

    def launch(args: List[str], hide: bool) -> Optional[subprocess.Popen]:
        print("[Start] Launching server with args:\n   " + " ".join(args))

        creationflags = 0
        if hide and os.name == "nt":
            # Hide the child window and keep it detached from our console
            CREATE_NO_WINDOW         = 0x08000000
            DETACHED_PROCESS         = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        try:
            if hide:
                # Fully quiet in headless: pipe stdio to NUL so UE doesn't try to attach
                with open(os.devnull, "wb") as devnull:
                    return subprocess.Popen(
                        args,
                        cwd=str(workdir),
                        stdin=devnull,
                        stdout=devnull,
                        stderr=devnull,
                        creationflags=creationflags,
                        close_fds=True,
                    )
            else:
                return subprocess.Popen(
                    args,
                    cwd=str(workdir),
                    creationflags=creationflags
                )
        except Exception as e:
            print(f"[Start] Failed to start server: {e}")
            return None

    # Primary attempt based on headless_mode
    args_primary = build_args(visible_console=not headless)
    proc = launch(args_primary, hide=headless)
    if proc is None:
        return None

    # If a headless launch dies immediately, fall back once to visible mode
    time.sleep(3)
    if headless and proc.poll() is not None:
        print("[Start] Headless server exited early. Falling back to visible console (-log).")
        args_fallback = build_args(visible_console=True)
        proc = launch(args_fallback, hide=False)
        if proc is None:
            return None
        time.sleep(2)

    # Mark server running (authoritative runtime flag)
    if proc.poll() is None:
        try:
            write_flag(proc.pid, os.path.basename(str(exe)), MAP_URL or "")
            PID_SERVER.write_text(str(proc.pid), encoding="utf-8")
            set_server_state(
                True,
                pid=proc.pid,
                last_start_utc=datetime.utcnow().isoformat() + "Z",
                exe=os.path.basename(str(exe)),
                cwd=str(workdir)
            )
        except Exception as e:
            print(f"[Start] Warning: failed to persist runtime state: {e}")

        return proc

def is_server_running() -> bool:
    return find_running_server() is not None

def win_creationflags_for_headless() -> int:
    """
    Return Windows creation flags that hide consoles for child processes.
    No-ops on non-Windows.
    """
    if os.name != "nt":
        return 0
    CREATE_NO_WINDOW        = 0x08000000
    DETACHED_PROCESS        = 0x00000008
    CREATE_NEW_PROCESS_GROUP= 0x00000200
    # NO_WINDOW is enough for python helpers; DETACHED avoids parent console binding.
    return CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

def headless_enabled() -> bool:
    try:
        return bool(config.get("headless_mode", False))
    except Exception:
        return False
        
def current_headless_flag() -> bool:
    """Return True if config['headless_mode'] is enabled."""
    try:
        return bool(config.get("headless_mode", False))
    except Exception:
        return False

# ----------------------------
# Backups / restore / prune (delegates to Controller/Tools/backups.py)
# ----------------------------

def _bk():
    """
    Lazy importer to avoid circular imports:
    - Tools/backups.py imports utils for Discord helpers.
    - So utils must only import backups at call time.
    """
    from Controller.Tools import backups as _backups  # type: ignore
    return _backups

def backup_save_file(
    save_path: Optional[Path] = None,   # kept for API compatibility (ignored)
    reason: str = "Manual",
    override_destination: Optional[Path] = None,
) -> Optional[Path]:
    """
    Thin shim: callers can keep using utils.backup_save_file().
    Behavior is provided by Tools/backups.make_backup().
    """
    try:
        # Tools/backups decides enablement + retention + paths.
        return _bk().make_backup(reason=reason, files=None, dst=override_destination)
    except Exception as e:
        print(f"[Backup] Shim failed: {e}")
        return None

def cleanup_old_backups(folder: Path) -> None:
    """
    Thin shim: callers can keep using utils.cleanup_old_backups(Path).
    If folder is provided, we honor it; otherwise per-reason pruning happens in backups.py.
    """
    try:
        _bk().prune_backups(path=folder)
    except Exception as e:
        print(f"[Backup] Cleanup shim failed: {e}")

def auto_restore_save_file(save_path: Optional[Path] = None) -> bool:
    """
    Restore a specific save filename from the newest archive that contains it.
    """
    try:
        target_name = (save_path or SAVE_FILE).name
        return bool(_bk().restore_from_latest(target_name))
    except Exception as e:
        print(f"[Restore] Shim failed: {e}")
        return False

# ----------------------------
# SteamCMD update (config-gated)
# ----------------------------
def check_for_steam_update() -> bool:
    """
    Run SteamCMD update for the configured app_id (retries + timeout).
    Fully gated by features.enable_steam_update.
    """
    if not is_feature_enabled("enable_steam_update", True):
        return True  # off = no-op success

    if not STEAMCMD_PATH or not APP_ID:
        print("[Update] SteamCMD path or App ID missing; skipping update.")
        return False

    validate   = bool(config.get("steam_update_validate", True))
    beta       = str(config.get("steam_update_beta", "") or "")
    beta_pwd   = str(config.get("steam_update_beta_password", "") or "")
    retries    = int(config.get("steam_update_retries", 2))
    timeout    = int(config.get("steam_update_timeout_seconds", 900))

    app_arg = f"{APP_ID}"
    if beta:
        app_arg += f" -beta {beta}"
        if beta_pwd:
            app_arg += f" -betapassword {beta_pwd}"
    if validate:
        app_arg += " validate"

    cmd = [STEAMCMD_PATH, "+force_install_dir", str(SERVER_DIR),
           "+login", "anonymous", "+app_update", app_arg, "+quit"]

    print("[Update] Running SteamCMD update…")
    for attempt in range(1, retries + 2):
        try:
            proc = subprocess.run(
                cmd, cwd=str(SERVER_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=timeout, check=False,
            )
            out = proc.stdout or ""
            ok = ("Success! App" in out) or ("fully installed" in out) or (proc.returncode == 0)
            if ok:
                print("[Update] SteamCMD update completed successfully.")
                send_discord_message("✅ SteamCMD update completed.", channel="startup")
                return True
            else:
                print(f"[Update] Attempt {attempt} failed — retrying…")
                print(out[-400:])
        except subprocess.TimeoutExpired:
            print("[Update] SteamCMD timed out; retrying…")
        except Exception as e:
            print(f"[Update] SteamCMD error: {e}; retrying…")
        time.sleep(5)

    send_discord_message("⚠️ SteamCMD update failed after retries.", channel="startup")
    print("[Update] SteamCMD update failed after retries.")
    return False

# ----------------------------
# Log rotation (optional)
# ----------------------------
def rotate_log_file(src: Path, dst: Path) -> bool:
    """
    Rotate log on Windows:
      1) os.replace with retries (preferred)
      2) fallback: copy2 + truncate (keeps the writer handle alive)
    """
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    last_err: Optional[Exception] = None
    for _ in range(LOG_ROTATION_RETRIES):
        try:
            os.replace(str(src), str(dst))
            print(f"[Logs] Rotated {src.name} -> {dst.name}")
            return True
        except (PermissionError, OSError) as e:
            last_err = e
            time.sleep(LOG_ROTATION_RETRY_SLEEP_SECONDS)

    try:
        shutil.copy2(str(src), str(dst))
        with open(src, "w", encoding="utf-8", errors="ignore"):
            pass
        print(f"[Logs] Copied+truncated {src.name} -> {dst.name} (in-use fallback)")
        return True
    except Exception as e:
        print(f"[Logs] Rotation failed after fallback: {e} (last replace error: {last_err})")
        return False

def rotate_server_log() -> None:
    """Rotate Vein.log into a timestamped ZIP in LOGS_DIR (feature-gated)."""
    if not bool(config.get("features", {}).get("enable_log_rotation", True)):
        return
    src = LOGS_DIR / "Vein.log"
    if not src.exists():
        return
    ts = _timestamp().replace(":", "-")
    raw_copy = LOGS_DIR / f"Vein-backup-{ts}.log"
    zip_copy = LOGS_DIR / f"{raw_copy.name}.zip"
    if not rotate_log_file(src, raw_copy):
        print("[Logs] Rotation skipped due to errors.")
        return
    try:
        with zipfile.ZipFile(zip_copy, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(raw_copy, arcname=raw_copy.name)
        raw_copy.unlink(missing_ok=True)
        print(f"[Logs] Rotated and zipped: {zip_copy.name}")
    except Exception as e:
        print(f"[Logs] Zip step failed: {e}")

# ----------------------------
# Monitor helpers
# ----------------------------
def stop_log_monitor() -> None:
    """Best-effort stop for the log monitor process (monitor_log.py)."""
    try:
        for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmd = p.info.get("cmdline") or []
                if any("monitor_log.py" in part for part in cmd):
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

def stop_crash_monitor() -> None:
    """Optional helper to stop crash_monitor.py processes cleanly."""
    try:
        for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmd = p.info.get("cmdline") or []
                if any("crash_monitor.py" in part for part in cmd):
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

# ----------------------------
# Orchestration helpers (restart + quiet windows)
# ----------------------------
def initiate_controlled_restart(reason: str = "unknown") -> bool:
    """
    Fire-and-forget restart respecting a simple throttle window.
    Writes a small lock to avoid duplicate spawns.
    """
    throttle_seconds = int(config.get("restart_throttle_seconds", 120))
    now = _now()
    try:
        if RESTART_STAMP.exists():
            try:
                last = float(RESTART_STAMP.read_text().strip() or "0")
                if (now - last) < throttle_seconds:
                    print(f"[Restart] Throttled ({int(now - last)}s since last).")
                    return False
            except Exception:
                pass

        if RESTARTING_LOCK.exists():
            return False

        RESTARTING_LOCK.write_text(reason, encoding="utf-8")
        # Ensure child sees the same config and launcher
        env = os.environ.copy()
        # carry current config path if one is already set in the parent
        if os.environ.get("VEIN_CONFIG"):
            env["VEIN_CONFIG"] = os.environ["VEIN_CONFIG"]
        # ensure children know how to spawn python helpers (used by start_server to spawn monitors)
        env.setdefault("PYEXE", sys.executable)  # prefer exact interpreter over "py -3"

        # Hide child console if headless
        creationflags = win_creationflags_for_headless()

        send_discord_message(f"🔄 Crash monitor initiated controlled restart (reason={reason}).", channel="startup")

        subprocess.Popen(
            [sys.executable, str(START_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env=env,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        RESTART_STAMP.write_text(str(now), encoding="utf-8")

        # Give start_server a short head start to create startup lock/quiet window
        time.sleep(int(config.get("restart_settle_seconds", 5)))
        return True
    finally:
        try:
            RESTARTING_LOCK.unlink(missing_ok=True)
        except Exception:
            pass

def create_startup_lock() -> None:
    try:
        STARTUP_LOCK.write_text(str(int(_now())), encoding="utf-8")
    except Exception:
        pass

def clear_startup_lock() -> None:
    try:
        STARTUP_LOCK.unlink(missing_ok=True)
    except Exception:
        pass

def startup_grace_active(max_age_seconds: int = 180) -> bool:
    """True if 'startup_in_progress.lock' is fresh (prevents false crash handling mid-boot)."""
    try:
        if not STARTUP_LOCK.exists():
            return False
        age = _now() - STARTUP_LOCK.stat().st_mtime
        return age <= max_age_seconds
    except Exception:
        return False

def set_autorestart_quiet_period(seconds: int = 120) -> None:
    """During this window, monitors should not trigger restarts."""
    try:
        QUIET_UNTIL.write_text(str(int(_now() + max(0, seconds))), encoding="utf-8")
    except Exception:
        pass

def autorestart_quiet_active() -> bool:
    try:
        if not QUIET_UNTIL.exists():
            return False
        until = int(QUIET_UNTIL.read_text(encoding="utf-8").strip() or "0")
        return _now() < until
    except Exception:
        return False

# ----------------------------
# Config summary helpers
# ----------------------------
def resolve_server_executable(
    server_dir: Path = SERVER_DIR,
    names: Optional[List[str]] = None
) -> Optional[Path]:
    return _choose_executable(server_dir, names or EXECUTABLE_NAMES)

def summarize_config() -> Dict[str, object]:
    exe = resolve_server_executable(SERVER_DIR, EXECUTABLE_NAMES)
    bview = backups_cfg()  # unified, migrated view of backups.*
    return {
        "server_dir": str(SERVER_DIR),
        "backup_root": str(bview.get("root") or get_path("backup_root")),
        "save_dir": str(SAVE_DIR),
        "logs_dir": str(LOGS_DIR),
        "executable_selected": str(exe) if exe else None,
        "executable_candidates": EXECUTABLE_NAMES,
        "map_url": MAP_URL,
        "max_players": MAX_PLAYERS,
        "game_port": GAME_PORT,
        "query_port": QUERY_PORT,
        "multi_home_ip": MULTI_HOME_IP,
        "steamcmd_path": STEAMCMD_PATH or None,
        "monitor_log_wait_timeout_seconds": int(config.get("monitor_log_wait_timeout_seconds", 60)),
        "headless": headless,
        "app_id": APP_ID or None,
        "features": {
            "enable_discord": bool(config.get("features", {}).get("enable_discord", True)),
            # keep for legacy UI until you remove it:
            "enable_backups (legacy)": bool(config.get("features", {}).get("enable_backups", True)),
            "enable_steam_update": bool(config.get("features", {}).get("enable_steam_update", True)),
            "enable_crash_monitor": bool(config.get("features", {}).get("enable_crash_monitor", True)),
            "enable_log_rotation": bool(config.get("features", {}).get("enable_log_rotation", True)),
            "enable_query_port": bool(config.get("enable_query_port", True)),
        },
        # expose canonical backups view for the Manager UI
        "backups": {
            "enable": bool(bview.get("enable", True)),
            "root": bview.get("root"),
            "folders": bview.get("folders"),
            "retention": bview.get("retention"),
        },
    }