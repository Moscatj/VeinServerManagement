# Controller/Tools/backups.py
from __future__ import annotations

import os, json, time, shutil, zipfile, hashlib, sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import asdict, dataclass, is_dataclass

from Tools.config_io import load_and_validate_config
from .state_io import write_state, now_iso
from Tools.discord import send_discord_message, is_discord_channel_enabled
from Tools.backup_pins import is_archive_pinned, read_backup_pin


class BackupError(Exception):
    """A hard failure while attempting a backup (e.g., IO/zip errors)."""


class BackupSkip(BackupError):
    """A soft skip (feature disabled, no save found, etc.)."""


@dataclass(frozen=True)
class BackupArchive:
    """Read-only archive metadata used by backup history surfaces."""

    path: str
    filename: str
    category: str
    modified: str
    size_bytes: int
    pinned: bool = False
    pin_label: str = ""
    pin_note: str = ""
    pin_status: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _active_cfg_path() -> Path:
    """Honor VEIN_CONFIG; otherwise prefer YAML then JSON in Config/."""
    env = os.environ.get("VEIN_CONFIG", "").strip()
    if env and Path(env).exists():
        return Path(env)

    cfg_dir = Path(__file__).resolve().parents[2] / "Config"
    for pat in ("*.yaml", "*.yml", "*.json"):
        cands = sorted(cfg_dir.glob(pat))
        if cands:
            return cands[0]
    raise BackupError(
        "No configuration found. Set VEIN_CONFIG or place YAML/JSON under Config/."
    )


def _cfg_to_dict(v):
    """Normalize ValidConfig/dataclass/dict to a plain dict."""
    if isinstance(v, dict):
        return v
    # common adapters
    if hasattr(v, "to_dict") and callable(v.to_dict):
        return v.to_dict()
    if hasattr(v, "as_dict") and callable(v.as_dict):
        return v.as_dict()
    if is_dataclass(v):
        return asdict(v)
    # last-resort: pull known attrs we use in backups.py
    out = {}
    for k in (
        "backups",
        "features",
        "paths",
        "save_dir",
        "server_dir",
        "backup_root",
        "runtime_dir",
        "max_backups",
        "backup_max_age_days",
        "backup_folders",
    ):
        if hasattr(v, k):
            out[k] = getattr(v, k)
    return out


def _cfg() -> dict:
    """Load the active config fresh each call (no caching)."""
    cfg_path = _active_cfg_path()
    vcfg = load_and_validate_config(str(cfg_path), fatal=False)  # returns ValidConfig
    return _cfg_to_dict(vcfg) or {}


# --- Runtime state writer (lazy; no new hard deps) ---------------------------


def _runtime_dir() -> Path:
    try:
        cfg = _cfg()
        p = cfg.get("runtime_dir") or (cfg.get("paths", {}) or {}).get("runtime_dir")
        return Path(p) if p else (Path(__file__).resolve().parents[2] / "Runtime")
    except Exception:
        return Path(__file__).resolve().parents[2] / "Runtime"


def _safe_mkdir(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _count_all() -> dict:
    """Return counts by reason and TOTAL."""
    counts = {}
    total = 0
    try:
        root = _root()
        folders = _folders()
        for reason, sub in folders.items():
            d = root / sub
            n = len([p for p in d.glob("*.zip") if p.is_file()]) if d.exists() else 0
            counts[reason] = n
            total += n
        # also include any loose zips directly under root
        if root.exists():
            loose = len([p for p in root.glob("*.zip") if p.is_file()])
            total += loose
    except Exception:
        pass
    counts["TOTAL"] = total
    return counts


def _write_backup_state(*, last_reason: str | None, last_zip: Path | None) -> None:
    """
    Write Runtime/backup.state.json with last backup info and per-reason counts.
    Uses state_io.write_state() for atomic, timestamped writes.
    """
    try:
        rt = _runtime_dir()
        _safe_mkdir(rt)
        state_path = rt / "backup.state.json"

        payload = {
            "schema": "1.0",
            "last_reason": last_reason,
            "last_zip": (last_zip.name if isinstance(last_zip, Path) else None),
            "last_path": (str(last_zip) if isinstance(last_zip, Path) else None),
            "last_utc": now_iso(),
            "counts": _count_all(),
            "root": str(_root()),
        }

        write_state(state_path, payload)
    except Exception as e:
        print(f"[Backup] state write failed: {e}")


# -----------------------------
# Config helpers
# -----------------------------
def _b(cfg_path: str, default=None):
    b = _cfg().get("backups") or {}
    cur = b
    for part in cfg_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _save_dir() -> Path:
    cfg = _cfg()
    # The config loader projects automatic/advanced SaveGames into this single
    # canonical value so backups cannot silently watch a different folder.
    sd = cfg.get("save_dir")
    if sd:
        return Path(str(sd))

    # Legacy compatibility for callers that provide an unresolved config.
    b = cfg.get("backups") or {}
    sd = b.get("save_dir")
    if sd:
        return Path(str(sd))

    sd = (cfg.get("paths", {}) or {}).get("save_dir")
    if sd:
        return Path(str(sd))

    # Fallback: derive from server_dir
    server_dir = cfg.get("server_dir")
    if server_dir:
        return Path(server_dir) / "Vein" / "Saved" / "SaveGames"

    # Last-ditch project-relative guess
    return Path(__file__).resolve().parents[3] / "Vein" / "Saved" / "SaveGames"


def _save_filenames() -> list[str]:
    cfg = _cfg()
    names = _b("save_filenames")
    if isinstance(names, list) and names:
        return [str(n) for n in names]
    names = cfg.get("save_filenames")
    if isinstance(names, list) and names:
        return [str(n) for n in names]
    return ["Server.vns"]


def _feature_enabled() -> bool:
    cfg = _cfg()
    backup_cfg = cfg.get("backups") or {}
    if "enabled" in backup_cfg:
        return bool(backup_cfg["enabled"])
    if "enable" in backup_cfg:
        return bool(backup_cfg["enable"])
    return bool((cfg.get("features", {}) or {}).get("enable_backups", True))


def _root() -> Path:
    cfg = _cfg()
    r = _b("root") or cfg.get("backup_root")
    return Path(str(r)) if r else (Path(__file__).resolve().parents[2] / "Backups")


def _folders() -> Dict[str, str]:
    cfg = _cfg()
    f = _b("folders") or cfg.get("backup_folders", {})
    return dict(f or {})


def _retention_for(reason: str) -> dict[str, int | bool]:
    cfg = _cfg()
    ret = _b("retention", {}) or {}
    rc = ret.get(reason) or {}
    dc = ret.get("default") or {}
    max_count = rc.get("max_backups", dc.get("max_backups", cfg.get("max_backups", 10)))
    max_age = rc.get(
        "max_age_days", dc.get("max_age_days", cfg.get("backup_max_age_days", 7))
    )
    return {
        "enabled": bool(rc.get("enabled", dc.get("enabled", True))),
        "by_count": bool(rc.get("by_count", dc.get("by_count", True))),
        "by_age": bool(rc.get("by_age", dc.get("by_age", True))),
        "minimum_backups": int(
            rc.get("minimum_backups", dc.get("minimum_backups", 3))
        ),
        "max_backups": int(max_count),
        "max_age_days": int(max_age),
    }


def _discord_flags() -> Dict[str, bool]:
    d = _b("discord", {}) or {}
    return {
        "on_create": bool(d.get("notify_on_create", True)),
        "on_prune": bool(d.get("notify_on_prune", False)),
    }


def _save_candidates() -> List[Path]:
    sd = _save_dir()
    return [sd / n for n in _save_filenames()]


def _dest_for(reason: str) -> Path:
    sub = _folders().get(reason, reason)
    return _root() / sub


# -----------------------------
# Utilities
# -----------------------------
def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pick_existing_save() -> Optional[Path]:
    for c in _save_candidates():
        if c.exists():
            return c
    # Helpful debug if nothing is found
    try:
        msg = " | ".join(map(str, _save_candidates()))
    except Exception:
        msg = "<error building candidate list>"
    print(f"[Backup] No save found. Checked: {msg}")
    if is_discord_channel_enabled("backups"):
        send_discord_message(
            f"Backup skipped: save file not found. Checked: `{msg}`",
            channel="backups",
        )
    return None


def _write_manifest(
    zf: zipfile.ZipFile,
    *,
    reason: str,
    save_name: str,
    src_path: Path,
    size: int,
    sha: str,
) -> None:
    manifest = {
        "reason": reason,
        "created_utc": now_iso(),
        "save_filename": save_name,
        "bytes": size,
        "sha256": sha,
        "config_digest": str(hash(repr(_cfg()))),
        "tool": "Controller/Tools/backups.py",
        "version": 1,
    }
    zf.writestr("manifest.json", json.dumps(manifest, indent=2))


# --- Log snapshot config (separate from save backups) ------------------------
def _log_root() -> Path:
    cfg = _cfg()
    # allow overrides
    r = cfg.get("log_backup_root") or (cfg.get("paths", {}) or {}).get(
        "log_backup_root"
    )
    if r:
        return Path(str(r))
    # default: Backups\Logs under the standard backup root
    return _root() / "Logs"


def _log_retention() -> dict:
    cfg = _cfg()
    keep = cfg.get("log_backup_max_files", 100)
    days = cfg.get("log_backup_max_age_days", 30)
    return {"max_files": int(keep), "max_age_days": int(days)}


def export_log_snapshot(src: Path, *, label: str | None = None) -> Path | None:
    """
    Copy+zip a log snapshot to Backups\\Logs with a timestamped name.
    Does NOT touch or truncate the live log file.
    """
    try:
        if not src or not src.exists():
            return None
        dst_root = _log_root()
        dst_root.mkdir(parents=True, exist_ok=True)

        stamp = now_iso().replace(":", "-").replace(".", "-")
        base = f"Vein-log-{label + '_' if label else ''}{stamp}.log"
        raw = dst_root / base
        zip_p = dst_root / (base + ".zip")

        shutil.copy2(src, raw)
        with zipfile.ZipFile(zip_p, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(raw, arcname=raw.name)
        raw.unlink(missing_ok=True)

        # optional: Discord breadcrumb (channel “monitor” keeps it consistent)
        try:
            if is_discord_channel_enabled("monitor"):
                send_discord_message(
                    f"Log snapshot archived: `{zip_p.name}`", channel="monitor"
                )
        except Exception:
            pass

        _prune_log_snapshots()
        return zip_p
    except Exception as e:
        print(f"[Logs] export_log_snapshot() failed: {e}")
        return None


def _prune_log_snapshots() -> dict:
    """Count/age prune for Backups\\Logs."""
    policy = _log_retention()
    root = _log_root()
    root.mkdir(parents=True, exist_ok=True)

    deleted = 0
    zips = sorted(
        [p for p in root.glob("*.log.zip") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    # by count
    while len(zips) > policy["max_files"]:
        old = zips.pop(0)
        try:
            old.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            pass
    # by age
    cutoff = time.time() - policy["max_age_days"] * 86400
    for p in list(zips):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink(missing_ok=True)
                deleted += 1
        except Exception:
            pass
    return {"deleted": deleted}


# -----------------------------
# Public API
# -----------------------------
def list_backup_archives(
    root: Path, *, limit: int | None = 200
) -> list[BackupArchive]:
    """Return newest ZIP archives below ``root`` without opening or modifying them."""
    root = Path(root)
    if not root.is_dir():
        return []
    entries: list[tuple[float, BackupArchive]] = []
    for path in root.rglob("*.zip"):
        try:
            if not path.is_file():
                continue
            stat = path.stat()
            relative_parent = path.parent.relative_to(root)
            category = "Root" if not relative_parent.parts else " / ".join(relative_parent.parts)
            modified = datetime.fromtimestamp(stat.st_mtime).astimezone().strftime(
                "%Y-%m-%d %H:%M:%S %Z"
            )
            entries.append(
                (
                    stat.st_mtime,
                    BackupArchive(
                        path=str(path),
                        filename=path.name,
                        category=category,
                        modified=modified,
                        size_bytes=stat.st_size,
                        pinned=(pin := read_backup_pin(path)) is not None,
                        pin_label=pin.label if pin else "",
                        pin_note=pin.note if pin else "",
                        pin_status=pin.status if pin else "",
                    ),
                )
            )
        except (OSError, ValueError):
            continue
    entries.sort(key=lambda item: item[0], reverse=True)
    selected = entries if limit is None else entries[: max(1, int(limit))]
    return [entry for _, entry in selected]


def manual_backup_main() -> int:
    """Create one manual backup for the active CLI configuration."""
    try:
        path = make_backup("Manual")
        print(f"Backup created: {path}")
        return 0
    except BackupSkip as exc:
        print(f"Backup skipped: {exc}")
        return 2
    except BackupError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1


def make_backup(
    reason: str, files: list[Path] | None = None, *, dst: Path | None = None
) -> Optional[Path]:
    """
    Create a timestamped ZIP containing the current save (and optional extra files).
    Raises:
        BackupSkip  - soft skip (feature disabled, no save found)
        BackupError - hard failure (I/O etc.)
    Returns:
        Path to created zip on success.
    """
    # 0) feature gate
    if not _feature_enabled():
        msg = "Backups are disabled (backups.enable=false)."
        print(f"[Backup] {msg}")
        if is_discord_channel_enabled("backups"):
            send_discord_message(msg, channel="backups")
        raise BackupSkip(msg)

    # 1) pick source
    src = None
    if files and len(files) == 1 and isinstance(files[0], Path):
        src = files[0]
    else:
        src = _pick_existing_save()
    if not src:
        # _pick_existing_save already printed a detailed "Checked: ..." list
        msg = f"No save file found in {_save_dir()}."
        raise BackupSkip(msg)

    # 2) destination
    dest_dir = dst or _dest_for(reason)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        msg = f"Unable to create backups folder: {dest_dir} ({e})"
        print(f"[Backup] {msg}")
        if is_discord_channel_enabled("backups"):
            send_discord_message(msg, channel="backups")
        raise BackupError(msg)

    # 3) build name
    stamp = now_iso().replace(":", "-").replace(".", "-")
    zip_path = dest_dir / f"Server_{reason}_{stamp}.zip"

    # 4) safe temp copy + zip
    tmp = dest_dir / f".tmp_copy_{stamp}_{src.name}"
    try:
        shutil.copy2(src, tmp)
        sha = _sha256(tmp)
        size = tmp.stat().st_size

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp, arcname=src.name)
            if files:
                for extra in files:
                    try:
                        if (
                            isinstance(extra, Path)
                            and extra.exists()
                            and extra.resolve() != src.resolve()
                        ):
                            zf.write(extra, arcname=f"extra/{extra.name}")
                    except Exception:
                        pass
            _write_manifest(
                zf, reason=reason, save_name=src.name, src_path=src, size=size, sha=sha
            )

        if _discord_flags()["on_create"] and is_discord_channel_enabled("backups"):
            send_discord_message(
                f"Backup created: `{zip_path.name}`", channel="backups"
            )

        prune_backups(reason)
        try:
            _write_backup_state(last_reason=reason, last_zip=zip_path)
        except Exception:
            pass
        print(f"[Backup] Created {zip_path}")
        return zip_path

    except BackupSkip:
        raise
    except Exception as e:
        msg = f"Failed to write archive {zip_path} ({e})"
        print(f"[Backup] {msg}")
        if is_discord_channel_enabled("backups"):
            send_discord_message(msg, channel="backups")
        raise BackupError(msg)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def prune_backups(reason: str | None = None, *, path: Path | None = None) -> dict:
    """
    Prune by per-reason count/age policy without crossing its safety floor.

    The newest ``minimum_backups`` archives are never automatic-cleanup
    candidates. Returns ``{'deleted': int}``.
    """
    folder = path or (_dest_for(reason) if reason else _root())
    folder.mkdir(parents=True, exist_ok=True)
    policy = _retention_for(reason or "default")
    cleanup_enabled = bool(policy["enabled"])
    by_count = bool(policy["by_count"])
    by_age = bool(policy["by_age"])
    minimum_backups = max(1, int(policy["minimum_backups"]))
    max_count = int(policy["max_backups"])
    max_age = int(policy["max_age_days"])

    deleted = 0
    zips = sorted(
        [p for p in folder.glob("*.zip") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    pinned = {archive for archive in zips if is_archive_pinned(archive)}
    unpinned = [archive for archive in zips if archive not in pinned]
    protected = set(unpinned[-minimum_backups:]) | pinned
    now = datetime.now()
    for p in list(zips):
        if p in protected:
            continue
        age_days = (now - datetime.fromtimestamp(p.stat().st_mtime)).days
        over_age = cleanup_enabled and by_age and age_days > max_age
        unpinned_count = sum(1 for archive in zips if archive not in pinned)
        over_count = cleanup_enabled and by_count and unpinned_count > max_count
        if over_age or over_count:
            try:
                p.unlink(missing_ok=True)
                zips.remove(p)
                deleted += 1
            except Exception:
                pass

    if (
        deleted
        and _discord_flags()["on_prune"]
        and is_discord_channel_enabled("backups")
    ):
        send_discord_message(
            f"Pruned {deleted} old backups in `{folder.name}`.", channel="backups"
        )
        # Update state after pruning (even if 0 deletions) so counts stay fresh
    try:
        _write_backup_state(last_reason=None, last_zip=None)
    except Exception:
        pass
    return {"deleted": deleted}


def latest_backup(reason: str | None = None) -> Optional[Path]:
    candidates: List[Path] = []
    if reason:
        d = _dest_for(reason)
        if d.exists():
            candidates.extend(d.glob("*.zip"))
    else:
        # search all known folders + root
        for sub in set(_folders().values()):
            d = _root() / sub
            if d.exists():
                candidates.extend(d.glob("*.zip"))
        candidates.extend([p for p in _root().glob("*.zip") if p.is_file()])

    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def restore_from_latest(target_name: str) -> bool:
    """Retained compatibility entrypoint; unsafe direct extraction is disabled."""
    del target_name
    print(
        "[Restore] Legacy direct extraction is disabled. Use guarded manual restore "
        "or configured missing-save startup recovery."
    )
    return False
