# Controller/Tools/state_io.py  (new)
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json

STATE_SCHEMA_VERSION = "1.0"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def default_state(status="stopped", pid=None, headless=True, version=None) -> dict:
    return {
        "schema": STATE_SCHEMA_VERSION,
        "status": status,               # running | stopped | restart_pending
        "last_updated": now_iso(),      # ISO-8601 Z
        "uptime_seconds": 0,            # monitor-reported
        "pid": pid,
        "headless": bool(headless),
        "version": version or "unknown" # monitor code version
    }

def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = now_iso()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)

def bump_heartbeat(path: Path, incr_seconds: int = 0) -> dict:
    try:
        cur = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        cur = default_state()
    if incr_seconds:
        cur["uptime_seconds"] = int(cur.get("uptime_seconds", 0)) + int(incr_seconds)
    write_state(path, cur)
    return cur
