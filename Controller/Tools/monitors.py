from __future__ import annotations

from typing import Optional

import psutil  # type: ignore


__all__ = ["stop_log_monitor", "stop_crash_monitor", "stop_all_monitors"]


def _stop_processes(keyword: str) -> None:
    try:
        for p in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmd = p.info.get("cmdline") or []
                if any(keyword in part for part in cmd):
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
    _stop_processes("monitor_log.py")


def stop_crash_monitor() -> None:
    """Best-effort stop for the crash monitor process (crash_monitor.py)."""
    _stop_processes("crash_monitor.py")


def stop_all_monitors() -> None:
    """Stops both monitors."""
    stop_log_monitor()
    stop_crash_monitor()
