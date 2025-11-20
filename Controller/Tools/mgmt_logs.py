from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from config_helper import config, paths_cfg

__all__ = [
    "management_log_root",
    "subsystem_dir",
    "latest_log_path",
    "latest_log_file",
    "allocate_log_file",
    "allocate_stream_files",
    "available_subsystems",
    "iter_log_files",
    "manifest",
    "migrate_legacy_logs",
    "archive_all_logs",
    "is_archived_path",
]

_DEFAULT_LAYOUT = {
    "vein_manager": "gui",
    "gui": "gui",
    "monitor_log": "monitors/log_monitor",
    "crash_monitor": "monitors/crash_monitor",
    "start_server": "controller/start_server",
    "shutdown_server": "controller/shutdown_server",
    "http_api": "monitors/http_api",
}

_LATEST_FILE = ".latest.json"
_MANIFEST_FILE: Path | None = None
_MAX_MANIFEST_ENTRIES = 50


def _canon(name: str) -> str:
    return (name or "misc").strip().lower().replace(" ", "_")


def _default_root() -> Path:
    paths = paths_cfg()
    root = (
        paths.get("mgmt_log_dir")
        or config.get("mgmt_log_dir")
        or str(Path(__file__).resolve().parents[2] / "Logs")
    )
    path = Path(root).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


ROOT = _default_root()
_MANIFEST_FILE = ROOT / "manifest.json"


def _normalized_rel(path: str | None, fallback: str) -> str:
    if not path:
        return fallback
    rel = str(path).replace("\\", "/").strip().strip("/")
    return rel or fallback


def _load_layout() -> Dict[str, str]:
    layout = dict(_DEFAULT_LAYOUT)
    cfg_layout = (config.get("management_logs") or {}).get("layout") or {}
    for key, rel in cfg_layout.items():
        layout[_canon(key)] = _normalized_rel(str(rel), _canon(key))
    return layout


LAYOUT = _load_layout()


def available_subsystems(include_empty: bool = False) -> List[str]:
    subs: set[str] = set(LAYOUT.keys())
    subs.update(_load_manifest().keys())
    try:
        for entry in ROOT.iterdir():
            if entry.is_dir():
                has_logs = any(entry.glob("*.log"))
                if include_empty or has_logs:
                    subs.add(_canon(entry.name))
    except Exception:
        pass
    return sorted(subs)


def _retention_defaults() -> Dict[str, int]:
    cfg = (config.get("management_logs") or {}).get("retention") or {}
    base = {
        "max_files": int(cfg.get("max_files", 10) or 10),
        "max_age_days": int(cfg.get("max_age_days", 14) or 14),
    }
    per = cfg.get("per_subsystem") or {}
    out = {}
    for key, overrides in per.items():
        canon = _canon(key)
        merged = dict(base)
        try:
            merged["max_files"] = int(overrides.get("max_files", merged["max_files"]))
        except Exception:
            pass
        try:
            merged["max_age_days"] = int(
                overrides.get("max_age_days", merged["max_age_days"])
            )
        except Exception:
            pass
        out[canon] = merged
    base["per_subsystem"] = out
    return base


RETENTION = _retention_defaults()


def _archive_defaults() -> Dict[str, object]:
    cfg = (config.get("management_logs") or {}).get("archive") or {}
    root = cfg.get("root") or str(ROOT / "Archive")
    defaults = {
        "enabled": bool(cfg.get("enabled", True)),
        "root": Path(root).expanduser(),
        "max_files": int(cfg.get("max_files", 200) or 200),
        "max_age_days": int(cfg.get("max_age_days", 90) or 90),
    }
    defaults["root"].mkdir(parents=True, exist_ok=True)
    return defaults


ARCHIVE = _archive_defaults()
ARCHIVE_ROOT = ARCHIVE["root"]


def management_log_root() -> Path:
    return ROOT


def _subsystem_path(name: str) -> Path:
    canon = _canon(name)
    rel = LAYOUT.get(canon) or canon
    return ROOT / rel


def subsystem_dir(name: str) -> Path:
    path = _subsystem_path(name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _relative_to_root(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def _load_manifest() -> Dict[str, List[dict]]:
    if not _MANIFEST_FILE or not _MANIFEST_FILE.exists():
        return {}
    try:
        with _MANIFEST_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_manifest(payload: Dict[str, List[dict]]) -> None:
    if not _MANIFEST_FILE:
        return
    try:
        tmp = _MANIFEST_FILE.with_suffix(".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, _MANIFEST_FILE)
    except Exception:
        pass


def manifest(subsystem: Optional[str] = None) -> Dict[str, List[dict]]:
    data = _load_manifest()
    if not subsystem:
        return data
    canon = _canon(subsystem)
    return {canon: data.get(canon, [])}


def _latest_meta_path(subsystem: str) -> Path:
    return subsystem_dir(subsystem) / _LATEST_FILE


def _load_latest(subsystem: str) -> dict:
    path = _latest_meta_path(subsystem)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_latest(subsystem: str, mapping: Dict[str, Path]) -> None:
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "streams": {
            stream: str(path.name) for stream, path in mapping.items() if path
        },
    }
    meta = _latest_meta_path(subsystem)
    try:
        meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _record_manifest_entry(
    subsystem: str,
    mapping: Dict[str, Path],
    label: str,
    metadata: Optional[dict] = None,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "streams": {k: _relative_to_root(v) for k, v in mapping.items()},
        "metadata": metadata or {},
    }
    data = _load_manifest()
    canon = _canon(subsystem)
    bucket = data.setdefault(canon, [])
    bucket.insert(0, entry)
    if len(bucket) > _MAX_MANIFEST_ENTRIES:
        del bucket[_MAX_MANIFEST_ENTRIES :]
    _write_manifest(data)


def allocate_stream_files(
    subsystem: str,
    *,
    label: str | None = None,
    streams: Iterable[str] = ("stdout", "stderr"),
    timestamped: bool = True,
    record_latest: bool = True,
    metadata: Optional[dict] = None,
) -> Dict[str, Path]:
    subdir = subsystem_dir(subsystem)
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = (label or subsystem).strip() or subsystem
    out: Dict[str, Path] = {}
    for stream in streams:
        parts = [prefix]
        if timestamped:
            parts.append(now)
        if stream:
            parts.append(stream)
        filename = ".".join(parts) + ".log"
        out[str(stream)] = subdir / filename
    if record_latest:
        _save_latest(subsystem, out)
    _record_manifest_entry(subsystem, out, label or subsystem, metadata)
    _apply_retention(subsystem)
    return out


def allocate_log_file(
    subsystem: str,
    *,
    label: str | None = None,
    stream: str | None = "stdout",
    timestamped: bool = True,
    record_latest: bool = True,
    metadata: Optional[dict] = None,
) -> Path:
    mapping = allocate_stream_files(
        subsystem,
        label=label,
        streams=(stream or "stdout",),
        timestamped=timestamped,
        record_latest=record_latest,
        metadata=metadata,
    )
    return mapping.get(stream or "stdout")  # type: ignore[return-value]


def latest_log_path(subsystem: str, stream: str | None = "stdout") -> Optional[Path]:
    subdir = subsystem_dir(subsystem)
    meta = _load_latest(subsystem)
    streams = meta.get("streams") or {}
    candidate = streams.get(stream or "stdout")
    if candidate:
        path = subdir / candidate
        if path.exists():
            return path
    pattern = "*.log" if not stream else f"*.{stream}.log"
    candidates = sorted(
        [p for p in subdir.glob(pattern) if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def latest_log_file(subsystem: str) -> Optional[Path]:
    for path in iter_log_files(subsystem):
        return path
    return None


def _retention_for(subsystem: str) -> dict:
    canon = _canon(subsystem)
    base = {
        "max_files": RETENTION["max_files"],
        "max_age_days": RETENTION["max_age_days"],
    }
    per = RETENTION.get("per_subsystem") or {}
    if canon in per:
        base.update(per[canon])
    return base


def _active_files(subsystem: str) -> set[Path]:
    meta = _load_latest(subsystem)
    subdir = subsystem_dir(subsystem)
    streams = meta.get("streams") or {}
    active: set[Path] = set()
    for rel in streams.values():
        p = subdir / rel
        if p.exists():
            active.add(p)
    return active


def _archive_dir(subsystem: str) -> Optional[Path]:
    if not ARCHIVE.get("enabled", True):
        return None
    rel = _normalized_rel(LAYOUT.get(_canon(subsystem)), _canon(subsystem))
    dest = ARCHIVE["root"] / rel
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _maybe_archive(subsystem: str, path: Path) -> Path | None:
    dest_root = _archive_dir(subsystem)
    if not dest_root:
        return None
    target = dest_root / path.name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = dest_root / f"{stem}.{int(time.time())}{suffix}"
    try:
        shutil.move(str(path), str(target))
    except Exception:
        return None
    _prune_archive(dest_root)
    return target


def _prune_archive(dest: Path) -> None:
    max_files = int(ARCHIVE.get("max_files", 200) or 200)
    max_age_days = int(ARCHIVE.get("max_age_days", 90) or 90)
    cutoff_ts = (datetime.now() - timedelta(days=max_age_days)).timestamp()
    files = sorted(
        [p for p in dest.glob("*.log") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for idx, path in enumerate(files):
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if idx < max_files and mtime >= cutoff_ts:
            continue
        try:
            path.unlink()
        except Exception:
            continue


def _apply_retention(subsystem: str) -> None:
    limits = _retention_for(subsystem)
    max_files = limits.get("max_files", 10)
    max_age_days = limits.get("max_age_days", 14)
    cutoff_ts = (datetime.now() - timedelta(days=max_age_days)).timestamp()
    subdir = subsystem_dir(subsystem)
    active = _active_files(subsystem)
    files = sorted(
        [p for p in subdir.glob("*.log") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    kept = 0
    for path in files:
        if path in active:
            continue
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if kept < max_files and mtime >= cutoff_ts:
            kept += 1
            continue
        _maybe_archive(subsystem, path)


_LEGACY_HINTS: Dict[str, tuple[str, ...]] = {
    "vein_manager": ("veinmanager", "vein_manager", "gui"),
    "monitor_log": ("monitor_log", "logmonitor"),
    "crash_monitor": ("crash_monitor", "crashmon"),
    "start_server": ("start_server", "server.stdout", "server_stdout"),
    "shutdown_server": ("shutdown_server", "stop_server"),
    "http_api": ("http_api",),
}


def _infer_subsystem_from_name(name: str) -> Optional[str]:
    lowered = name.lower()
    for subsystem, hints in _LEGACY_HINTS.items():
        if any(h in lowered for h in hints):
            return subsystem
    if lowered.endswith(".stdout.log") or lowered.endswith(".stderr.log"):
        return "vein_manager"
    return None


def _unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    counter = 1
    while True:
        candidate = dest.with_name(f"{stem}.{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _guess_stream(name: str) -> str:
    lowered = name.lower()
    if "stderr" in lowered or lowered.endswith(".err.log"):
        return "stderr"
    return "stdout"


def migrate_legacy_logs(*, dry_run: bool = False) -> list[tuple[Path, Path]]:
    """
    Move top-level legacy log files into their subsystem folders.
    Returns list of (source, destination) tuples.
    """
    moves: list[tuple[Path, Path]] = []
    candidates: list[Path] = []
    for child in ROOT.iterdir():
        if child.is_file() and child.suffix.lower() == ".log":
            candidates.append(child)

    legacy_dir = ROOT / "Old"
    if legacy_dir.exists():
        for path in legacy_dir.rglob("*.log"):
            if path.is_file():
                candidates.append(path)

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        subsystem = _infer_subsystem_from_name(path.name) or "misc"
        dest_dir = _subsystem_path(subsystem)
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
        dest = _unique_destination(dest_dir / path.name)
        moves.append((path, dest))
        if dry_run:
            continue
        try:
            shutil.move(str(path), str(dest))
        except Exception:
            continue
        stream = _guess_stream(path.name)
        _record_manifest_entry(
            subsystem, {stream: dest}, label=f"legacy:{path.stem}", metadata={"migrated": True}
        )
        try:
            path.parent.rmdir()
        except OSError:
            pass
    return moves


def archive_logs(
    subsystem: str, *, include_active: bool = False
) -> list[tuple[Path, Path]]:
    """
    Move current log files into Archive/, skipping active ones unless include_active is True.
    """
    moved: list[tuple[Path, Path]] = []
    active = set() if include_active else _active_files(subsystem)
    for path in _iter_live_logs(subsystem):
        if not include_active and path in active:
            continue
        dest = _maybe_archive(subsystem, path)
        if dest:
            moved.append((path, dest))
    return moved


def archive_all_logs(*, include_active: bool = False) -> list[tuple[Path, Path]]:
    """
    Archive logs for every known subsystem.
    """
    results: list[tuple[Path, Path]] = []
    for subsystem in available_subsystems(include_empty=True):
        results.extend(archive_logs(subsystem, include_active=include_active))
    return results


def is_archived_path(path: Path) -> bool:
    try:
        candidate = Path(path).resolve()
    except Exception:
        candidate = Path(path)
    try:
        candidate.relative_to(ARCHIVE_ROOT)
        return True
    except Exception:
        return False


def iter_log_files(subsystem: str, include_archive: bool = False) -> Iterator[Path]:
    """
    Yield log files for a subsystem sorted by newest first.
    """
    yield from _iter_live_logs(subsystem)
    if include_archive:
        yield from _iter_archived_logs(subsystem)


def _iter_live_logs(subsystem: str) -> Iterator[Path]:
    base = subsystem_dir(subsystem)
    yield from _iter_sorted_logs(base)


def _iter_archived_logs(subsystem: str) -> Iterator[Path]:
    rel = _normalized_rel(LAYOUT.get(_canon(subsystem)), _canon(subsystem))
    archive_dir = ARCHIVE_ROOT / rel
    if not archive_dir.exists():
        return
    yield from _iter_sorted_logs(archive_dir)


def _iter_sorted_logs(folder: Path) -> Iterator[Path]:
    try:
        files = sorted(
            [p for p in folder.glob("*.log") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except FileNotFoundError:
        return
    for path in files:
        yield path
