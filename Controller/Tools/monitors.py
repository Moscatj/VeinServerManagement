from __future__ import annotations

import psutil  # type: ignore


__all__ = ["stop_log_monitor", "stop_crash_monitor", "stop_all_monitors"]


def _matches_monitor_command(cmdline: list[str], script_name: str, packaged_name: str) -> bool:
    for part in cmdline:
        value = str(part).lower()
        if value.endswith(script_name) or value == packaged_name:
            return True
    return False


def _stop_processes(script_name: str, packaged_name: str) -> None:
    try:
        for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmd = p.info.get("cmdline") or []
                if _matches_monitor_command(cmd, script_name, packaged_name):
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass


def stop_log_monitor() -> None:
    """Best-effort stop for the log monitor process (monitor_log.py)."""
    _stop_processes("monitor_log.py", "monitor-log")


def stop_crash_monitor() -> None:
    """Best-effort stop for the crash monitor process (crash_monitor.py)."""
    _stop_processes("crash_monitor.py", "crash-monitor")


def stop_all_monitors() -> None:
    """Stops both monitors."""
    stop_log_monitor()
    stop_crash_monitor()
