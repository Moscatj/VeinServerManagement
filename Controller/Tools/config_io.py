# Controller/Tools/config_io.py  (replace/minify)
from __future__ import annotations
from pathlib import Path
import json, sys

REQUIRED_KEYS = ["server_dir","runtime_dir","logs_dir","save_dir","monitor","steam","backups"]

def load_config(cfg_path: str) -> dict:
    p = Path(cfg_path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"[FATAL] Could not read config: {e}")

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        sys.exit(f"[FATAL] Missing required keys in config: {missing}")

    # Path sanity (existence checks where it matters)
    for k in ("server_dir","runtime_dir"):
        if not Path(data[k]).exists():
            print(f"[WARN] Path does not exist: {k} -> {data[k]}")

    # Preferred exe must be in list if set
    pe = data.get("preferred_exe")
    if pe and pe not in data.get("server_executables", []):
        print(f"[WARN] preferred_exe '{pe}' not found in server_executables; launcher will fallback.")

    # Heartbeat clamps
    mon = data["monitor"]
    mon["heartbeat_seconds"] = max(5, int(mon.get("heartbeat_seconds", 60)))
    mon["fresh_window_multiplier"] = float(mon.get("fresh_window_multiplier", 2.0))
    return data
