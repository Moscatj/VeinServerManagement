"""Read-only validation for a future guarded backup restore workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from Tools.backup_pins import read_backup_pin


@dataclass(frozen=True)
class RestorePreview:
    archive: str
    archive_size: int
    archive_modified: str
    archive_valid: bool
    manifest_valid: bool
    save_member: str
    save_size: int
    save_sha256: str
    reason: str
    created_utc: str
    destination: str
    destination_exists: bool
    destination_size: int
    server_running: bool
    restore_point_label: str
    restore_point_note: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready_for_guarded_restore(self) -> bool:
        return (
            self.archive_valid
            and self.manifest_valid
            and bool(self.save_member)
            and not self.server_running
        )

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["ready_for_guarded_restore"] = self.ready_for_guarded_restore
        return payload


def _safe_member_name(name: str) -> bool:
    normalized = str(name).replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(
        normalized
        and not normalized.startswith("/")
        and not path.is_absolute()
        and ".." not in path.parts
        and not (path.parts and path.parts[0].endswith(":"))
    )


def _stream_sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def inspect_restore_archive(
    archive: Path,
    *,
    save_dir: Path,
    server_running: bool,
) -> RestorePreview:
    """Inspect one archive without writing or extracting any file."""
    archive = Path(archive)
    save_dir = Path(save_dir)
    errors: list[str] = []
    warnings: list[str] = []
    archive_size = 0
    archive_modified = ""
    manifest_valid = False
    save_member = ""
    save_size = 0
    save_sha256 = ""
    reason = ""
    created_utc = ""
    destination = save_dir

    try:
        stat = archive.stat()
        archive_size = stat.st_size
        archive_modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
    except OSError as exc:
        errors.append(f"Archive is unavailable: {exc}")

    if not errors and archive.suffix.casefold() != ".zip":
        errors.append("The selected file is not a ZIP archive.")

    if not errors:
        try:
            with zipfile.ZipFile(archive, "r") as bundle:
                members = bundle.infolist()
                unsafe = [item.filename for item in members if not _safe_member_name(item.filename)]
                if unsafe:
                    errors.append("Archive contains an unsafe path and cannot be restored.")
                names = [item.filename for item in members]
                normalized_names = [
                    name.replace("\\", "/").casefold() for name in names
                ]
                if len(normalized_names) != len(set(normalized_names)):
                    errors.append("Archive contains duplicate member names.")
                damaged = bundle.testzip()
                if damaged:
                    errors.append(f"Archive integrity check failed at {damaged}.")

                manifest: dict = {}
                if "manifest.json" not in names:
                    warnings.append("Backup manifest is missing; guarded restore is unavailable.")
                else:
                    try:
                        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
                        if not isinstance(manifest, dict):
                            raise ValueError("manifest must be an object")
                    except (KeyError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
                        errors.append(f"Backup manifest is invalid: {exc}")

                if manifest:
                    reason = str(manifest.get("reason") or "")
                    created_utc = str(manifest.get("created_utc") or "")
                    declared_save = str(manifest.get("save_filename") or "")
                    declared_sha = str(manifest.get("sha256") or "").casefold()
                    if not declared_save or declared_save not in names:
                        errors.append("Manifest save file is missing from the archive.")
                    elif not _safe_member_name(declared_save):
                        errors.append("Manifest save file path is unsafe.")
                    else:
                        save_member = declared_save
                        info = bundle.getinfo(declared_save)
                        save_size = info.file_size
                        with bundle.open(info, "r") as stream:
                            save_sha256 = _stream_sha256(stream)
                        if not declared_sha:
                            errors.append("Manifest does not contain a save-file SHA-256 hash.")
                        elif save_sha256 != declared_sha:
                            errors.append("Save-file hash does not match the backup manifest.")
                        else:
                            manifest_valid = True
                        destination = save_dir / Path(declared_save).name
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            errors.append(f"Archive could not be read: {exc}")

    if server_running:
        warnings.append("Stop the server before a guarded restore can run.")

    pin = read_backup_pin(archive)
    destination_exists = destination.is_file()
    try:
        destination_size = destination.stat().st_size if destination_exists else 0
    except OSError:
        destination_exists = False
        destination_size = 0

    return RestorePreview(
        archive=str(archive),
        archive_size=archive_size,
        archive_modified=archive_modified,
        archive_valid=not errors,
        manifest_valid=manifest_valid,
        save_member=save_member,
        save_size=save_size,
        save_sha256=save_sha256,
        reason=reason,
        created_utc=created_utc,
        destination=str(destination),
        destination_exists=destination_exists,
        destination_size=destination_size,
        server_running=bool(server_running),
        restore_point_label=pin.label if pin else "",
        restore_point_note=pin.note if pin else "",
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
