# Controller/Tools/process.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, List

import psutil  # type: ignore
import subprocess

# For now, we delegate to the existing implementations in utils.py.
# This lets newer code import a clean process API from Tools.process
# without rewriting everything at once.

from utils import (
    find_running_server as _find_running_server,
    start_vein_server as _start_vein_server,
    stop_vein_server as _stop_vein_server,
    stop_all_vein_processes_aggressive as _stop_all_vein_processes_aggressive,
)


def find_running_server(
    executable_names: Optional[List[str]] = None,
    server_dir: Optional[Path] = None,
) -> Optional[psutil.Process]:
    """
    Thin wrapper around utils.find_running_server.

    Returns the psutil.Process for a running Vein server, or None.
    """
    return _find_running_server(executable_names=executable_names, server_dir=server_dir)


def start_server(
    max_players: int = None,
    ip: str = None,
    server_dir: Optional[Path] = None,
    extra_args: Optional[List[str]] = None,
    *,
    executable: Optional[str] = None,
    cwd: Optional[str | Path] = None,
) -> Optional[subprocess.Popen]:
    """
    Wrapper around utils.start_vein_server.

    All parameters are passed through; we just provide a slightly more
    generic name for tools to call.
    """
    kwargs = {
        "extra_args": extra_args,
        "executable": executable,
        "cwd": cwd,
    }

    # Only pass max_players/ip if explicitly provided so we preserve
    # utils.start_vein_server defaults.
    if max_players is not None:
        kwargs["max_players"] = max_players
    if ip is not None:
        kwargs["ip"] = ip
    if server_dir is not None:
        kwargs["server_dir"] = server_dir

    return _start_vein_server(**kwargs)


def stop_server(timeout: int | None = None) -> bool:
    """
    Wrapper around utils.stop_vein_server.

    Attempts a graceful stop, then force-kill if needed (as implemented
    in utils). Returns True if we believe the server has stopped.
    """
    return _stop_vein_server(timeout=timeout)


def stop_all_servers_aggressive() -> list[int]:
    """
    Wrapper around utils.stop_all_vein_processes_aggressive.

    Stops ALL Vein server processes (any variant) and their child trees.
    Returns list of PIDs we acted upon.
    """
    return _stop_all_vein_processes_aggressive()


def is_server_running() -> bool:
    """
    Convenience helper using find_running_server.

    Returns True if any Vein server process is detected.
    """
    return find_running_server() is not None
