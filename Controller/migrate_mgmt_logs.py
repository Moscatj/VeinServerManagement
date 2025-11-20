from __future__ import annotations

import argparse
from pathlib import Path

from Tools import mgmt_logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move legacy management logs into per-subsystem folders."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which files would be moved without touching the filesystem.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    moves = mgmt_logs.migrate_legacy_logs(dry_run=args.dry_run)
    if not moves:
        print("No legacy logs found in Logs/.")
        return 0

    action = "Would move" if args.dry_run else "Moved"
    for src, dest in moves:
        print(f"{action}: {Path(src)} -> {Path(dest)}")
    print(f"{action} {len(moves)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
