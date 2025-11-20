from __future__ import annotations

import argparse
from typing import List

from Tools import log_search, mgmt_logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search management logs across subsystems.")
    parser.add_argument(
        "--subsystem",
        action="append",
        help="Subsystem to include (repeatable). Defaults to all with logs.",
    )
    parser.add_argument(
        "--search",
        help="Regex pattern to match. If omitted, prints entire files within the limit.",
    )
    parser.add_argument("--since", help="Only include files newer than this window (e.g., 2h, 30m, 1d).")
    parser.add_argument("--limit", type=int, default=200, help="Maximum matches to print (default 200).")
    parser.add_argument(
        "--case-sensitive", action="store_true", help="Make regex matching case-sensitive."
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Search archived logs in addition to current logs.",
    )
    parser.add_argument("--list", action="store_true", help="List known subsystems and exit.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        for name in mgmt_logs.available_subsystems(include_empty=True):
            print(name)
        return 0

    since_ts = log_search.parse_since(args.since)
    subsystems: List[str] = []
    if args.subsystem:
        subsystems = [s.strip() for s in args.subsystem if s.strip()]

    hits = log_search.search_logs(
        subsystems=subsystems or None,
        pattern=args.search,
        case_sensitive=args.case_sensitive,
        since_ts=since_ts,
        max_hits=args.limit,
        include_archive=args.include_archive,
    )
    if not hits:
        print("No matches.")
        return 0
    print(log_search.format_hits(hits))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
