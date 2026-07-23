"""Pinned backup metadata and cleanup protection helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from .state_io import now_iso

PIN_SUFFIX = ".vein-pin.json"
PIN_SCHEMA = 1


class BackupPinError(ValueError):
    """Raised when pinned-backup metadata cannot be created safely."""


@dataclass(frozen=True)
class BackupPin:
    label: str
    note: str
    pinned_utc: str
    archive_sha256: str
    status: str = "valid"

    def as_dict(self) -> dict:
        return asdict(self)


def pin_sidecar_path(archive: Path) -> Path:
    archive = Path(archive)
    return archive.with_name(f"{archive.name}{PIN_SUFFIX}")


def is_archive_pinned(archive: Path) -> bool:
    """Treat sidecar presence as protection, even when its content is damaged."""
    return pin_sidecar_path(archive).is_file()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_backup_pin(archive: Path) -> BackupPin | None:
    sidecar = pin_sidecar_path(archive)
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or int(data.get("schema", 0)) != PIN_SCHEMA:
            raise ValueError("unsupported pin metadata")
        return BackupPin(
            label=str(data.get("label") or "Pinned backup"),
            note=str(data.get("note") or ""),
            pinned_utc=str(data.get("pinned_utc") or ""),
            archive_sha256=str(data.get("archive_sha256") or ""),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return BackupPin(
            label="Pinned backup (metadata needs attention)",
            note="The pin metadata could not be read. Cleanup protection remains active.",
            pinned_utc="",
            archive_sha256="",
            status="invalid",
        )


def pin_backup(archive: Path, *, label: str, note: str = "") -> BackupPin:
    """Atomically add or replace metadata for an existing ZIP archive."""
    archive = Path(archive)
    return _write_backup_pin(archive, label=label, note=note, preserve_time=False)


def update_backup_pin(archive: Path, *, label: str, note: str = "") -> BackupPin:
    """Update restore-point details without changing the archive or pin time."""
    archive = Path(archive)
    if not is_archive_pinned(archive):
        raise BackupPinError("The selected backup is not a restore point.")
    return _write_backup_pin(archive, label=label, note=note, preserve_time=True)


def _write_backup_pin(
    archive: Path, *, label: str, note: str, preserve_time: bool
) -> BackupPin:
    clean_label = " ".join(str(label).split()).strip()
    clean_note = str(note).strip()
    if not archive.is_file() or archive.suffix.casefold() != ".zip":
        raise BackupPinError("Select an existing backup ZIP archive.")
    if not clean_label:
        raise BackupPinError("A restore-point label is required.")
    if len(clean_label) > 80:
        raise BackupPinError("The restore-point label must be 80 characters or fewer.")
    if len(clean_note) > 500:
        raise BackupPinError("The restore-point note must be 500 characters or fewer.")

    current = read_backup_pin(archive) if preserve_time else None
    pinned_utc = (
        current.pinned_utc
        if current is not None and current.status == "valid" and current.pinned_utc
        else now_iso()
    )
    pin = BackupPin(
        label=clean_label,
        note=clean_note,
        pinned_utc=pinned_utc,
        archive_sha256=_sha256(archive),
    )
    sidecar = pin_sidecar_path(archive)
    temporary = sidecar.with_suffix(f"{sidecar.suffix}.tmp")
    payload = {
        "schema": PIN_SCHEMA,
        "archive": archive.name,
        **pin.as_dict(),
    }
    try:
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(sidecar)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise BackupPinError(f"Could not save restore-point metadata: {exc}") from exc
    return pin


def remove_backup_pin(archive: Path) -> bool:
    """Remove cleanup protection metadata without deleting the backup ZIP."""
    archive = Path(archive)
    sidecar = pin_sidecar_path(archive)
    if not archive.is_file() or archive.suffix.casefold() != ".zip":
        raise BackupPinError("Select an existing backup ZIP archive.")
    if not sidecar.is_file():
        raise BackupPinError("The selected backup is not a restore point.")
    try:
        sidecar.unlink()
    except OSError as exc:
        raise BackupPinError(f"Could not remove restore-point protection: {exc}") from exc
    return True
