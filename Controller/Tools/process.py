# Controller/Tools/process.py
from __future__ import annotations

import fnmatch
import os
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Sequence

import psutil  # type: ignore

from config_helper import config, get_path
from Tools.discord import send_discord_message
from Tools.runtime import (
    PID_SERVER,
    clear_runtime_markers,
    set_server_state,
    write_flag,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Canonical server settings
SERVER_DIR: Path = Path(get_path("server_dir"))
EXECUTABLE_NAMES: List[str] = list(config.get("server_executables", []))
MAP_URL: str = str(config.get("map_path", "/Game/Vein/Maps/ChamplainValley?listen"))
MAX_PLAYERS: int = int(config.get("max_players", 8))
GAME_PORT: int = int(config.get("game_port", 7777))
QUERY_PORT: int = int(config.get("query_port", 27015))
MULTI_HOME_IP: str = str(config.get("multi_home_ip", "0.0.0.0"))
ABSOLUTE_LOG_FILE: str = str(config.get("absolute_log_file", "") or "")
EXTRA_LAUNCH_ARGS: List[str] = list(config.get("extra_launch_args", []))
ENABLE_QUERY_PORT: bool = bool(config.get("enable_query_port", True))

# Image patterns / helpers used for aggressive cleanup
VEIN_IMAGE_PATTERNS = [
    "VeinServer.exe",
    "VeinServer-Win64-Test.exe",
    "VeinServer-*.exe",
]

VEIN_IMAGE_NAMES = [
    "VeinServer.exe",
    "VeinServer-Win64-Test.exe",
    "VeinServer-Win64-Shipping.exe",
    "VeinServer-Win64-Development.exe",
]

UE_HELPERS = [
    "CrashReportClient.exe",
    "UnrealCEFSubProcess.exe",
]

__all__ = [
    "find_running_server",
    "stop_server",
    "stop_all_servers_aggressive",
    "list_all_servers",
    "kill_process_tree",
    "is_server_running",
    "start_server",
    "start_vein_server",
    "win_creationflags_for_headless",
    "headless_enabled",
    "current_headless_flag",
    "resolve_server_executable",
]


def _exe_matches_any(name: str | None, patterns: list[str]) -> bool:
    if not name:
        return False
    name = name.strip()
    for pat in patterns:
        try:
            if fnmatch.fnmatch(name, pat):
                return True
        except Exception:
            pass
    return False


def _cmdline_head(info: dict[str, Any]) -> str:
    cmd = info.get("cmdline")
    head = ""
    try:
        if isinstance(cmd, (list, tuple)):
            head = str(cmd[0]) if cmd else ""
        elif isinstance(cmd, str) and cmd.strip():
            parts = shlex.split(cmd, posix=(os.name != "nt"))
            head = parts[0] if parts else ""
    except Exception:
        return ""
    return head.strip().strip('"')


def _cmdline_head_basename(info: dict[str, Any]) -> str:
    head = _cmdline_head(info)
    if not head:
        return ""
    return os.path.basename(head)


def _cmdline_head_fullpath(info: dict[str, Any]) -> str:
    head = _cmdline_head(info)
    if not head:
        return ""
    try:
        return str(Path(head).resolve())
    except Exception:
        try:
            return os.path.abspath(head)
        except Exception:
            return head


def _process_name_candidates(info: dict[str, Any]) -> list[str]:
    names: list[str] = []
    try:
        pname = str(info.get("name") or "").strip()
        if pname:
            names.append(pname)
    except Exception:
        pass
    head = _cmdline_head_basename(info)
    if head and head not in names:
        names.append(head)
    return names


def _matches_known_executables(info: dict[str, Any], names: Sequence[str]) -> bool:
    if not names:
        return False
    for cand in _process_name_candidates(info):
        if cand in names:
            return True
    return False


def _cwd_matches(info: dict[str, Any], target: str) -> bool:
    if not target:
        return False
    try:
        pcwd = info.get("cwd") or ""
        return bool(pcwd) and os.path.abspath(pcwd) == target
    except Exception:
        return False


def _choose_executable(server_dir: Path, names: List[str]) -> Optional[Path]:
    for name in names:
        cand = server_dir / name
        if cand.exists():
            return cand
    return None


def _is_vein_server_process(p: psutil.Process) -> bool:
    try:
        info = getattr(p, "info", {})
        for cand in _process_name_candidates(info):
            if _exe_matches_any(cand, VEIN_IMAGE_PATTERNS):
                return True
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def list_all_servers(verbose: bool = False) -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    for p in psutil.process_iter(attrs=["pid", "name", "cwd", "cmdline"]):
        try:
            if _is_vein_server_process(p):
                if verbose:
                    info = getattr(p, "info", {})
                    exe_hint = _cmdline_head(info)
                    print(f"[Find] PID={p.pid} name={info.get('name')} cmd={exe_hint}")
                procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def find_running_server(
    executable_names: Optional[List[str]] = None,
    server_dir: Optional[Path] = None,
) -> Optional[psutil.Process]:
    names = executable_names or EXECUTABLE_NAMES
    sdir = str((server_dir or SERVER_DIR).resolve())

    for p in psutil.process_iter(attrs=["pid", "name", "cwd", "cmdline"]):
        info = getattr(p, "info", {})
        try:
            if _cwd_matches(info, sdir) and _matches_known_executables(info, names):
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        info = getattr(p, "info", {})
        try:
            if _matches_known_executables(info, names):
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        if _is_vein_server_process(p):
            return p

    return None


def kill_process_tree(pid: int, timeout: int = 5) -> None:
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


def stop_server(timeout: int | None = None) -> bool:
    proc = find_running_server()
    if not proc:
        clear_runtime_markers()
        return True
    try:
        send_discord_message(
            "🛑 stop_vein_server(): requesting graceful shutdown of server process.",
            channel="startup",
        )
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout or int(config.get("shutdown_timeout_sec", 60)))
        clear_runtime_markers()
        set_server_state(False, pid=0, last_exit_code=0)
        return True
    except Exception:
        pass

    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        clear_runtime_markers()
        set_server_state(False, pid=0, last_exit_code=-1)
        return True
    except Exception:
        return False


def _powershell_kill_by_fullpaths(paths: list[str]) -> None:
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
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "; ".join(lines),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def stop_all_servers_aggressive() -> list[int]:
    acted: list[int] = []
    procs = list_all_servers(verbose=True)
    if not procs:
        return acted
    timeout = int(config.get("shutdown_timeout_sec", 60))

    send_discord_message(
        "🛑 stop_all_vein_processes_aggressive(): killing all VeinServer processes.",
        channel="startup",
    )

    for p in procs:
        try:
            acted.append(p.pid)
            kill_process_tree(p.pid, timeout=timeout)
        except Exception:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    for img in VEIN_IMAGE_NAMES:
        try:
            subprocess.run(
                ["taskkill", "/IM", img, "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    if bool(config.get("kill_ue_helpers_on_shutdown", True)):
        for img in UE_HELPERS:
            try:
                subprocess.run(
                    ["taskkill", "/IM", img, "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    leftovers = list_all_servers(verbose=True)
    if leftovers:
        exe_paths = []
        seen = set()
        for p in leftovers:
            try:
                info = getattr(p, "info", {})
                path = _cmdline_head_fullpath(info)
                if path and path not in seen:
                    seen.add(path)
                    exe_paths.append(path)
            except Exception:
                continue
        _powershell_kill_by_fullpaths(exe_paths)

    try:
        clear_runtime_markers()
        set_server_state(False, pid=0, last_exit_code=-1)
    except Exception:
        pass

    return sorted(set(acted))


def is_server_running() -> bool:
    return find_running_server() is not None


def win_creationflags_for_headless() -> int:
    if os.name != "nt":
        return 0
    CREATE_NO_WINDOW = 0x08000000
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    return CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP


def headless_enabled() -> bool:
    try:
        return bool(config.get("headless_mode", False))
    except Exception:
        return False


def current_headless_flag() -> bool:
    try:
        return bool(config.get("headless_mode", False))
    except Exception:
        return False


def _merged_launch_args(extra_from_call: Optional[List[str]]) -> List[str]:
    base = list(EXTRA_LAUNCH_ARGS or [])
    tail = list(extra_from_call or [])
    if not base:
        return tail
    if not tail:
        return base
    merged = list(base)
    for a in tail:
        try:
            i = merged.index(a)
            merged[i] = a
        except ValueError:
            merged.append(a)
    return merged


def start_server(
    max_players: int = MAX_PLAYERS,
    ip: str = MULTI_HOME_IP,
    server_dir: Path = SERVER_DIR,
    extra_args: Optional[List[str]] = None,
    *,
    executable: Optional[str] = None,
    cwd: Optional[str | Path] = None,
) -> Optional[subprocess.Popen]:
    if executable:
        exe = Path(executable).expanduser()
    else:
        exe = _choose_executable(server_dir, EXECUTABLE_NAMES)
        if not exe:
            print("[Start] No server executable found in candidates.")
            return None

    workdir = Path(cwd).expanduser() if cwd is not None else Path(server_dir)

    headless = headless_enabled()
    abs_log_file = ABSOLUTE_LOG_FILE

    def build_args(visible_console: bool) -> List[str]:
        args: List[str] = [str(exe)]
        map_url = (MAP_URL or "").strip()
        if map_url:
            args.append(map_url)
        if "-server" not in args:
            args.append("-server")
        if max_players and int(max_players) > 0:
            args.append(f"-MaxPlayers={int(max_players)}")
        if ip and ip != "0.0.0.0":
            args.append(f"-MultiHome={ip}")
        if GAME_PORT:
            args.append(f"-port={int(GAME_PORT)}")
        if ENABLE_QUERY_PORT and QUERY_PORT:
            args.append(f"-QueryPort={int(QUERY_PORT)}")
        if abs_log_file:
            args.append(f"-Abslog={abs_log_file}")

        if visible_console:
            if "-log" not in args:
                args.append("-log")
        else:
            try:
                while True:
                    args.remove("-log")
            except ValueError:
                pass

        args.extend(["-Unattended", "-NoCrashDialog"])
        args.extend(_merged_launch_args(extra_args))
        return args

    def launch(args: List[str], hide: bool) -> Optional[subprocess.Popen]:
        print("[Start] Launching server with args:\n   " + " ".join(args))
        creationflags = 0
        if hide and os.name == "nt":
            CREATE_NO_WINDOW = 0x08000000
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            creationflags = (
                CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            )
        try:
            if hide:
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
                    creationflags=creationflags,
                )
        except Exception as e:
            print(f"[Start] Failed to start server: {e}")
            return None

    args_primary = build_args(visible_console=not headless)
    proc = launch(args_primary, hide=headless)
    if proc is None:
        return None

    time.sleep(3)
    if headless and proc.poll() is not None:
        print(
            "[Start] Headless server exited early. Falling back to visible console (-log)."
        )
        args_fallback = build_args(visible_console=True)
        proc = launch(args_fallback, hide=False)
        if proc is None:
            return None
        time.sleep(2)

    if proc.poll() is None:
        try:
            write_flag(proc.pid, os.path.basename(str(exe)), MAP_URL or "")
            PID_SERVER.write_text(str(proc.pid), encoding="utf-8")
            set_server_state(
                True,
                pid=proc.pid,
                last_start_utc=datetime.utcnow().isoformat() + "Z",
                exe=os.path.basename(str(exe)),
                cwd=str(workdir),
            )
        except Exception as e:
            print(f"[Start] Warning: failed to persist runtime state: {e}")
    return proc


def start_vein_server(*args, **kwargs):
    return start_server(*args, **kwargs)


def resolve_server_executable(
    server_dir: Path = SERVER_DIR,
    names: Optional[List[str]] = None,
) -> Optional[Path]:
    return _choose_executable(server_dir, names or EXECUTABLE_NAMES)
