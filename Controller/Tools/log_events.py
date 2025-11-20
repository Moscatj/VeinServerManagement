from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from . import mgmt_logs

SEVERITY_PATTERNS = {
    "CRITICAL": ("fatal error", "unhandled exception", "panic", "traceback"),
    "ERROR": ("error", "exception", "failed", "traceback", "access violation"),
    "WARNING": ("warning", "warn", "retry", "timeout"),
}


@dataclass
class LogEvent:
    file: Path
    line_no: int
    level: str
    message: str
    timestamp: float


def _detect_level(line: str) -> str:
    lowered = line.lower()
    for level, patterns in SEVERITY_PATTERNS.items():
        if any(p in lowered for p in patterns):
            return level
    return "INFO"


def _should_capture(level: str, allowed: Sequence[str]) -> bool:
    return level.upper() in allowed


def scan_file(
    path: Path,
    *,
    allowed_levels: Sequence[str] = ("CRITICAL", "ERROR", "WARNING"),
    limit: Optional[int] = None,
) -> List[LogEvent]:
    events: List[LogEvent] = []
    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = 0.0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, line in enumerate(handle, 1):
                level = _detect_level(line)
                if not _should_capture(level, allowed_levels):
                    continue
                events.append(
                    LogEvent(
                        file=path,
                        line_no=idx,
                        level=level,
                        message=line.rstrip(),
                        timestamp=mtime,
                    )
                )
                if limit and len(events) >= limit:
                    break
    except FileNotFoundError:
        return events
    except Exception:
        return events
    return events


def scan_files(
    files: Iterable[Path],
    *,
    allowed_levels: Sequence[str] = ("CRITICAL", "ERROR", "WARNING"),
    per_file_limit: Optional[int] = None,
) -> List[LogEvent]:
    collected: List[LogEvent] = []
    for file in files:
        collected.extend(
            scan_file(file, allowed_levels=allowed_levels, limit=per_file_limit)
        )
    return collected


def collect_recent_events(
    subsystems: Sequence[str],
    *,
    since_ts: Optional[float] = None,
    per_file_limit: int = 20,
    max_events: int = 200,
    include_archive: bool = False,
    archive_only: bool = False,
) -> List[LogEvent]:
    events: List[LogEvent] = []
    since_ts = since_ts or 0.0
    for subsystem in subsystems:
        for path in mgmt_logs.iter_log_files(subsystem, include_archive=include_archive):
            is_archived = mgmt_logs.is_archived_path(path)
            if archive_only and not is_archived:
                continue
            if not include_archive and is_archived:
                continue
            try:
                mtime = path.stat().st_mtime
            except FileNotFoundError:
                continue
            if mtime < since_ts:
                continue
            events.extend(
                scan_file(
                    path,
                    allowed_levels=("CRITICAL", "ERROR", "WARNING"),
                    limit=per_file_limit,
                )
            )
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events[:max_events]
