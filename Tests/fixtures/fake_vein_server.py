"""Deterministic packaged-lifecycle fixture; never connects to Steam or a game server."""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _absolute_log_argument(argv: list[str]) -> Path | None:
    for argument in argv:
        if argument.lower().startswith("-abslog="):
            value = argument.split("=", 1)[1].strip().strip('"')
            return Path(value) if value else None
    return None


def main() -> int:
    log_path = _absolute_log_argument(sys.argv[1:])
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", buffering=1) as stream:
            stream.write("LogInit: Fake Vein lifecycle fixture started\n")
            stream.write("LogNet: GameNetDriver listening on port 7777\n")
            while True:
                stream.write("LogTemp: Fake Vein lifecycle heartbeat\n")
                time.sleep(1)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
