"""Bounded-test lifecycle worker; never connects to Steam, VEIN, or a network."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    for attempt in range(20):
        try:
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.01)


def _run_server(runtime: Path, game_log: Path) -> None:
    (runtime / "server.pid").write_text(str(os.getpid()), encoding="utf-8")
    _write_json(
        runtime / "server_state.json",
        {"status": "running", "process_running": True, "pid": os.getpid()},
    )
    game_log.parent.mkdir(parents=True, exist_ok=True)
    with game_log.open("a", encoding="utf-8", buffering=1) as stream:
        stream.write("LogInit: Fake lifecycle server started\n")
        time.sleep(0.1)
        stream.write("LogNet: GameNetDriver listening on port 7777\n")
        while True:
            time.sleep(0.1)


def _run_log_monitor(runtime: Path, game_log: Path) -> None:
    (runtime / "log_monitor.pid").write_text(str(os.getpid()), encoding="utf-8")
    state_path = runtime / "log_monitor.state.json"
    while True:
        try:
            joinable = "GameNetDriver listening" in game_log.read_text(encoding="utf-8")
        except OSError:
            joinable = False
        _write_json(
            state_path,
            {
                "active": True,
                "watching_server": True,
                "status": "tailing" if game_log.exists() else "waiting_for_log",
                "server_joinable": joinable,
                "pid": os.getpid(),
            },
        )
        time.sleep(0.05)


def _run_crash_monitor(runtime: Path) -> None:
    (runtime / "crash_monitor.pid").write_text(str(os.getpid()), encoding="utf-8")
    _write_json(
        runtime / "crash_monitor.state.json",
        {
            "active": True,
            "watching_server": True,
            "mode": "watching",
            "pid": os.getpid(),
        },
    )
    while True:
        time.sleep(0.1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("server", "log", "crash"), required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--game-log", type=Path, required=True)
    args = parser.parse_args()
    args.runtime.mkdir(parents=True, exist_ok=True)

    if args.role == "server":
        _run_server(args.runtime, args.game_log)
    elif args.role == "log":
        _run_log_monitor(args.runtime, args.game_log)
    else:
        _run_crash_monitor(args.runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
