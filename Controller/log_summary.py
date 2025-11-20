from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from Tools import log_events, mgmt_logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate JSON summaries of recent log errors/warnings."
    )
    parser.add_argument(
        "--subsystem",
        action="append",
        help="Subsystem to summarize (repeatable). Defaults to all with logs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum events per subsystem (default 50).",
    )
    parser.add_argument(
        "--per-file",
        type=int,
        default=20,
        help="Maximum events per file before moving on (default 20).",
    )
    return parser


def _serialize_events(events: List[log_events.LogEvent]) -> List[dict]:
    serialized = []
    for evt in events:
        try:
            rel = evt.file.relative_to(mgmt_logs.management_log_root())
        except Exception:
            rel = evt.file
        serialized.append(
            {
                "file": str(rel),
                "line": evt.line_no,
                "level": evt.level,
                "message": evt.message,
            }
        )
    return serialized


def summarize_subsystem(subsystem: str, limit: int, per_file: int) -> dict:
    events = log_events.collect_recent_events(
        [subsystem], since_ts=None, per_file_limit=per_file, max_events=limit
    )
    payload = {
        "subsystem": subsystem,
        "generated": datetime.now(timezone.utc).isoformat(),
        "events": _serialize_events(events),
    }
    dest = mgmt_logs.subsystem_dir(subsystem) / "summary.json"
    try:
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    subsystems = args.subsystem or mgmt_logs.available_subsystems()
    summaries: Dict[str, dict] = {}
    for subsystem in subsystems:
        summaries[subsystem] = summarize_subsystem(
            subsystem, args.limit, args.per_file
        )
    combined = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "summaries": summaries,
    }
    dest = mgmt_logs.management_log_root() / "summary.json"
    try:
        dest.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    except Exception:
        pass
    print(
        f"Wrote summaries for {len(summaries)} subsystem(s) to {dest.relative_to(mgmt_logs.management_log_root())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
