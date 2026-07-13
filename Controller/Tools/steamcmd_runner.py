"""Run one installer-owned SteamCMD process with cooperative cancellation."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TextIO


CANCELLED_EXIT_CODE = 20
POLL_SECONDS = 0.1
HEARTBEAT_SECONDS = 0.25
HEARTBEAT_LINE = "__VEIN_STEAMCMD_HEARTBEAT__"
PHASE_PREFIX = "__VEIN_STEAMCMD_PHASE__:"


def build_bootstrap_command(steamcmd_exe: Path) -> list[str]:
    """Build the first-run SteamCMD initialization command."""

    return [str(steamcmd_exe), "+quit"]


def build_command(steamcmd_exe: Path, server_dir: Path, app_id: str) -> list[str]:
    """Build the fixed anonymous Windows/public SteamCMD maintenance command."""

    return [
        str(steamcmd_exe),
        "+@sSteamCmdForcePlatformType",
        "windows",
        "+force_install_dir",
        str(server_dir),
        "+login",
        "anonymous",
        "+app_update",
        str(app_id),
        "-beta",
        "public",
        "validate",
        "+quit",
    ]


def _forward_output(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output.put(line)
    finally:
        output.put(None)


def _stop_owned_process(process: subprocess.Popen[str]) -> None:
    """Stop only the SteamCMD child created by this runner."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _emit_available(output: queue.Queue[str | None]) -> bool:
    reader_finished = False
    while True:
        try:
            line = output.get_nowait()
        except queue.Empty:
            break
        if line is None:
            reader_finished = True
            continue
        print(line.rstrip("\r\n"), flush=True)
    return reader_finished


def _run_owned_command(
    command: list[str],
    working_dir: Path,
    cancel_file: Path,
) -> int:
    """Run and stream one child command owned by this runner."""

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(working_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
    except OSError as exc:
        print(f"Unable to launch SteamCMD: {exc}", file=sys.stderr, flush=True)
        return 2

    assert process.stdout is not None
    output: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(
        target=_forward_output,
        args=(process.stdout, output),
        name="steamcmd-output",
        daemon=True,
    )
    reader.start()
    reader_finished = False
    next_heartbeat = 0.0

    while True:
        now = time.monotonic()
        if now >= next_heartbeat:
            print(HEARTBEAT_LINE, flush=True)
            next_heartbeat = now + HEARTBEAT_SECONDS
        reader_finished = _emit_available(output) or reader_finished
        if cancel_file.exists():
            print("SteamCMD cancellation requested; stopping this installer-owned process...", flush=True)
            _stop_owned_process(process)
            reader.join(timeout=2)
            _emit_available(output)
            print("SteamCMD operation cancelled. Partial files were preserved for a later retry.", flush=True)
            return CANCELLED_EXIT_CODE

        result = process.poll()
        if result is not None and reader_finished:
            return int(result)
        time.sleep(POLL_SECONDS)


def run_steamcmd(
    steamcmd_exe: Path,
    server_dir: Path,
    app_id: str,
    cancel_file: Path,
) -> int:
    """Initialize SteamCMD, then stream the server install/update operation."""

    steamcmd_exe = steamcmd_exe.resolve()
    server_dir = server_dir.resolve()
    cancel_file = cancel_file.resolve()
    if not steamcmd_exe.is_file():
        print(f"SteamCMD executable not found: {steamcmd_exe}", file=sys.stderr, flush=True)
        return 2

    print(f"{PHASE_PREFIX}bootstrap", flush=True)
    bootstrap_result = _run_owned_command(
        build_bootstrap_command(steamcmd_exe), steamcmd_exe.parent, cancel_file
    )
    if bootstrap_result == CANCELLED_EXIT_CODE:
        return bootstrap_result
    if bootstrap_result != 0:
        print(
            f"SteamCMD initialization returned {bootstrap_result}; attempting the server operation once with the initialized files.",
            file=sys.stderr,
            flush=True,
        )

    print(f"{PHASE_PREFIX}server", flush=True)
    return _run_owned_command(
        build_command(steamcmd_exe, server_dir, app_id),
        steamcmd_exe.parent,
        cancel_file,
    )


__all__ = [
    "CANCELLED_EXIT_CODE",
    "HEARTBEAT_LINE",
    "PHASE_PREFIX",
    "build_bootstrap_command",
    "build_command",
    "run_steamcmd",
]
