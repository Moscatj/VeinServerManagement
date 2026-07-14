from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psutil  # type: ignore


__all__ = [
    "request_monitor_stop_flags",
    "mark_monitor_stopped",
    "stop_log_monitor",
    "stop_crash_monitor",
    "stop_all_monitors",
]


def request_monitor_stop_flags(runtime_dir: Path) -> tuple[Path, Path]:
    """Keep both canonical stop requests asserted until the next startup."""
    runtime = Path(runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    paths = (
        runtime / "stop_log_monitor.flag",
        runtime / "stop_crash_monitor.flag",
    )
    for path in paths:
        path.write_text("intentional shutdown\n", encoding="utf-8")
    return paths


def mark_monitor_stopped(runtime_dir: Path, monitor_name: str) -> Path:
    """Persist terminal monitor state after a confirmed process stop."""
    names = {
        "log": ("log_monitor.state.json", "log_monitor.pid"),
        "crash": ("crash_monitor.state.json", "crash_monitor.pid"),
    }
    if monitor_name not in names:
        raise ValueError(f"Unknown monitor name: {monitor_name}")
    state_name, pid_name = names[monitor_name]
    runtime = Path(runtime_dir)
    state_path = runtime / state_name
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data.update(
        {
            "active": False,
            "watching_server": False,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    )
    if monitor_name == "log":
        data.update({"status": "stopped", "server_joinable": False})
    else:
        data["mode"] = "stopped"
    runtime.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, state_path)
    (runtime / pid_name).unlink(missing_ok=True)
    return state_path


def _matches_monitor_command(cmdline: list[str], script_name: str, packaged_name: str) -> bool:
    for part in cmdline:
        value = str(part).lower()
        if value.endswith(script_name) or value == packaged_name:
            return True
    return False


def _stop_processes(script_name: str, packaged_name: str) -> bool:
    stopped = True
    try:
        for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmd = p.info.get("cmdline") or []
                if _matches_monitor_command(cmd, script_name, packaged_name):
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except Exception:
                        stopped = False
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                stopped = False
                continue
    except Exception:
        stopped = False
    return stopped


def stop_log_monitor() -> bool:
    """Best-effort stop for the log monitor process (monitor_log.py)."""
    return _stop_processes("monitor_log.py", "monitor-log")


def stop_crash_monitor() -> bool:
    """Best-effort stop for the crash monitor process (crash_monitor.py)."""
    return _stop_processes("crash_monitor.py", "crash-monitor")


def stop_all_monitors() -> bool:
    """Stops both monitors."""
    log_stopped = stop_log_monitor()
    crash_stopped = stop_crash_monitor()
    return log_stopped and crash_stopped
