from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

from . import mgmt_logs

__all__ = ["SearchHit", "search_logs", "parse_since", "format_hits"]


@dataclass
class SearchHit:
    subsystem: str
    file: Path
    line_no: int
    text: str


def parse_since(expr: Optional[str]) -> Optional[float]:
    if not expr:
        return None
    expr = expr.strip().lower()
    if expr in ("all", "any"):
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if expr.isdigit():
        return time.time() - int(expr)
    suffix = expr[-1]
    value = expr[:-1]
    if suffix in units and value.replace(".", "", 1).isdigit():
        try:
            amount = float(value)
        except ValueError:
            return None
        return time.time() - amount * units[suffix]
    return None


def _iter_paths(
    subsystems: Sequence[str], include_archive: bool
) -> Iterator[tuple[str, Path, bool]]:
    for subsystem in subsystems:
        for path in mgmt_logs.iter_log_files(subsystem, include_archive=include_archive):
            yield subsystem, path, mgmt_logs.is_archived_path(path)


def search_logs(
    subsystems: Optional[Sequence[str]] = None,
    *,
    pattern: Optional[str] = None,
    case_sensitive: bool = False,
    since_ts: Optional[float] = None,
    max_hits: int = 500,
    include_archive: bool = False,
    archive_only: Optional[set[str]] = None,
) -> List[SearchHit]:
    subsystems = list(subsystems or mgmt_logs.available_subsystems())
    regex = None
    if pattern:
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
    hits: List[SearchHit] = []
    archive_only = archive_only or set()
    for subsystem, path, archived in _iter_paths(subsystems, include_archive):
        if archive_only and subsystem in archive_only and not archived:
            continue
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if since_ts and mtime < since_ts:
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for idx, line in enumerate(handle, 1):
                    text = line.rstrip()
                    if regex and not regex.search(text):
                        continue
                    hits.append(SearchHit(subsystem=subsystem, file=path, line_no=idx, text=text))
                    if len(hits) >= max_hits:
                        return hits
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return hits


def format_hits(hits: Iterable[SearchHit]) -> str:
    lines = []
    for hit in hits:
        try:
            rel = hit.file.relative_to(mgmt_logs.management_log_root())
        except Exception:
            rel = hit.file
        lines.append(f"[{hit.subsystem}] {rel}:{hit.line_no}: {hit.text}")
    return "\n".join(lines)
