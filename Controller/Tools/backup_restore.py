"""Guarded save restoration with mandatory safety backup and rollback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Callable
import uuid
import zipfile

from Tools.backup_pins import pin_backup
from Tools.backup_restore_preview import RestorePreview, inspect_restore_archive
from Tools.state_io import now_iso


class GuardedRestoreError(RuntimeError):
    """Raised when a guarded restore cannot complete safely."""


@dataclass(frozen=True)
class GuardedRestoreResult:
    archive: str
    destination: str
    safety_backup: str
    restored_sha256: str
    completed_utc: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StartupRecoveryResult:
    archive: str
    destination: str
    restored_sha256: str
    completed_utc: str

    def as_dict(self) -> dict:
        return asdict(self)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_hash(path: Path, expected: str) -> bool:
    try:
        return path.is_file() and _hash_file(path) == expected
    except OSError:
        return False


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _stage_archive_save(
    archive: Path, *, save_member: str, expected_sha256: str, stage_path: Path
) -> None:
    """Extract one already-validated save to a private verified staging file."""
    with zipfile.ZipFile(archive, "r") as bundle, bundle.open(
        save_member, "r"
    ) as source, stage_path.open("wb") as staged:
        shutil.copyfileobj(source, staged, length=1024 * 1024)
        staged.flush()
        os.fsync(staged.fileno())
    if not _verify_hash(stage_path, expected_sha256):
        raise GuardedRestoreError("The staged save failed hash verification.")


def guarded_restore(
    archive: Path,
    *,
    save_dir: Path,
    operation_dir: Path,
    server_running_check: Callable[[], bool],
    create_safety_backup: Callable[[Path], Path],
) -> GuardedRestoreResult:
    """Restore one validated save while retaining a verified rollback path.

    The caller supplies the authoritative server-state check and the existing
    backup workflow. This function never starts/stops a server and never deletes
    a backup archive.
    """
    archive = Path(archive)
    save_dir = Path(save_dir)
    operation_dir = Path(operation_dir)
    operation_id = uuid.uuid4().hex
    lock_path = operation_dir / "restore.lock"
    journal_path = operation_dir / "restore.state.json"
    stage_path = save_dir / f".vein-restore-stage-{operation_id}.tmp"
    rollback_path = save_dir / f".vein-restore-rollback-{operation_id}.tmp"
    lock_fd: int | None = None
    destination: Path | None = None
    safety_backup: Path | None = None
    original_sha = ""
    replaced = False
    preserve_rollback = False

    try:
        operation_dir.mkdir(parents=True, exist_ok=True)
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, operation_id.encode("ascii"))
        except FileExistsError as exc:
            raise GuardedRestoreError(
                "Another restore operation is active or requires recovery."
            ) from exc

        if server_running_check():
            raise GuardedRestoreError("Stop the server before restoring a save.")

        preview = inspect_restore_archive(
            archive, save_dir=save_dir, server_running=False
        )
        if not preview.ready_for_guarded_restore:
            findings = "; ".join(preview.errors + preview.warnings)
            raise GuardedRestoreError(
                f"Selected archive did not pass restore validation: {findings}"
            )
        destination = Path(preview.destination)
        if not destination.is_file():
            raise GuardedRestoreError(
                "The current live save was not found. This guarded restore phase "
                "requires an existing save so it can create and verify a rollback point."
            )

        _write_json(
            journal_path,
            {
                "schema": 1,
                "operation_id": operation_id,
                "phase": "validating_current_save",
                "archive": str(archive),
                "destination": str(destination),
                "started_utc": now_iso(),
            },
        )
        original_sha = _hash_file(destination)
        shutil.copy2(destination, rollback_path)
        if not _verify_hash(rollback_path, original_sha):
            raise GuardedRestoreError("Could not verify the temporary rollback copy.")

        safety_backup = Path(create_safety_backup(destination))
        safety_preview = inspect_restore_archive(
            safety_backup, save_dir=save_dir, server_running=False
        )
        if not safety_preview.ready_for_guarded_restore:
            raise GuardedRestoreError(
                "The mandatory Before Restore safety backup did not pass validation."
            )
        if safety_preview.save_sha256 != original_sha:
            raise GuardedRestoreError(
                "The mandatory Before Restore safety backup does not match the current "
                "live save. No save was replaced."
            )
        pin_backup(
            safety_backup,
            label=f"Before Restore {now_iso()}",
            note=f"Automatic safety point before restoring {archive.name}.",
        )

        _write_json(
            journal_path,
            {
                "schema": 1,
                "operation_id": operation_id,
                "phase": "staging",
                "archive": str(archive),
                "destination": str(destination),
                "safety_backup": str(safety_backup),
                "original_sha256": original_sha,
            },
        )
        _stage_archive_save(
            archive,
            save_member=preview.save_member,
            expected_sha256=preview.save_sha256,
            stage_path=stage_path,
        )
        if server_running_check():
            raise GuardedRestoreError(
                "The server started during restore preparation; no save was replaced."
            )

        _write_json(
            journal_path,
            {
                "schema": 1,
                "operation_id": operation_id,
                "phase": "replacing",
                "archive": str(archive),
                "destination": str(destination),
                "safety_backup": str(safety_backup),
                "original_sha256": original_sha,
                "replacement_sha256": preview.save_sha256,
            },
        )
        os.replace(stage_path, destination)
        replaced = True
        if not _verify_hash(destination, preview.save_sha256):
            raise GuardedRestoreError(
                "Post-restore verification failed; restoring the prior live save."
            )

        rollback_path.unlink(missing_ok=True)
        result = GuardedRestoreResult(
            archive=str(archive),
            destination=str(destination),
            safety_backup=str(safety_backup),
            restored_sha256=preview.save_sha256,
            completed_utc=now_iso(),
        )
        _write_json(
            journal_path,
            {"schema": 1, "phase": "complete", **result.as_dict()},
        )
        return result
    except Exception as exc:
        failure = (
            exc
            if isinstance(exc, GuardedRestoreError)
            else GuardedRestoreError(f"Guarded restore failed: {exc}")
        )
        if replaced and destination is not None and rollback_path.is_file():
            try:
                os.replace(rollback_path, destination)
                rollback_verified = _verify_hash(destination, original_sha)
            except OSError:
                rollback_verified = False
                preserve_rollback = rollback_path.is_file()
            if not rollback_verified:
                try:
                    _write_json(
                        journal_path,
                        {
                            "schema": 1,
                            "phase": "rollback_failed",
                            "archive": str(archive),
                            "destination": str(destination),
                            "safety_backup": str(safety_backup or ""),
                            "rollback_copy": (
                                str(rollback_path) if preserve_rollback else ""
                            ),
                            "error": str(failure),
                        },
                    )
                except OSError:
                    pass
                raise GuardedRestoreError(
                    "Restore failed and automatic rollback could not be verified. "
                    f"Use the pinned safety backup: {safety_backup or 'unavailable'}"
                ) from exc
            try:
                _write_json(
                    journal_path,
                    {
                        "schema": 1,
                        "phase": "failed_rolled_back",
                        "archive": str(archive),
                        "destination": str(destination),
                        "safety_backup": str(safety_backup or ""),
                        "error": str(failure),
                    },
                )
            except OSError:
                pass
        if failure is exc:
            raise
        raise failure from exc
    finally:
        stage_path.unlink(missing_ok=True)
        if not preserve_rollback:
            rollback_path.unlink(missing_ok=True)
        if lock_fd is not None:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)


def recover_missing_save(
    archives: list[Path],
    *,
    save_dir: Path,
    expected_filenames: list[str],
    operation_dir: Path,
    server_running_check: Callable[[], bool],
) -> StartupRecoveryResult:
    """Atomically recover a missing save from the newest valid backup.

    This is intentionally narrower than a manual restore: it never replaces an
    existing file. Archives are supplied newest-first and each is validated
    before one is staged and activated.
    """
    save_dir = Path(save_dir)
    operation_dir = Path(operation_dir)
    expected = {Path(name).name.casefold() for name in expected_filenames if name}
    if not expected:
        expected = {"server.vns"}
    operation_id = uuid.uuid4().hex
    lock_path = operation_dir / "restore.lock"
    journal_path = operation_dir / "startup_recovery.state.json"
    stage_path = save_dir / f".vein-recovery-stage-{operation_id}.tmp"
    failed_path = save_dir / f".vein-recovery-failed-{operation_id}.tmp"
    lock_fd: int | None = None
    destination: Path | None = None
    activated = False

    try:
        operation_dir.mkdir(parents=True, exist_ok=True)
        save_dir.mkdir(parents=True, exist_ok=True)
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, operation_id.encode("ascii"))
        except FileExistsError as exc:
            raise GuardedRestoreError(
                "Another restore operation is active or requires recovery."
            ) from exc

        if server_running_check():
            raise GuardedRestoreError(
                "The server is already running; startup recovery was cancelled."
            )
        existing = [save_dir / name for name in expected_filenames]
        if any(path.exists() for path in existing):
            raise GuardedRestoreError(
                "A live save appeared before recovery; no file was replaced."
            )

        selected: tuple[Path, RestorePreview] | None = None
        rejected: list[str] = []
        for candidate in map(Path, archives):
            preview = inspect_restore_archive(
                candidate, save_dir=save_dir, server_running=False
            )
            if (
                preview.archive_valid
                and preview.manifest_valid
                and bool(preview.save_member)
                and Path(preview.destination).name.casefold() in expected
                and preview.save_size > 0
            ):
                selected = (candidate, preview)
                break
            rejected.append(candidate.name)
        if selected is None:
            detail = f" Checked {len(rejected)} archive(s)." if rejected else ""
            raise GuardedRestoreError(
                "No valid save backup is available for automatic recovery." + detail
            )

        archive, preview = selected
        destination = Path(preview.destination)
        _write_json(
            journal_path,
            {
                "schema": 1,
                "operation_id": operation_id,
                "phase": "staging",
                "archive": str(archive),
                "destination": str(destination),
                "started_utc": now_iso(),
            },
        )
        _stage_archive_save(
            archive,
            save_member=preview.save_member,
            expected_sha256=preview.save_sha256,
            stage_path=stage_path,
        )
        if server_running_check():
            raise GuardedRestoreError(
                "The server started during recovery preparation; no save was restored."
            )
        if destination.exists():
            raise GuardedRestoreError(
                "A live save appeared during recovery; no file was replaced."
            )

        os.replace(stage_path, destination)
        activated = True
        if not _verify_hash(destination, preview.save_sha256):
            raise GuardedRestoreError(
                "The recovered save failed post-write verification. Do not start the server."
            )
        result = StartupRecoveryResult(
            archive=str(archive),
            destination=str(destination),
            restored_sha256=preview.save_sha256,
            completed_utc=now_iso(),
        )
        _write_json(
            journal_path, {"schema": 1, "phase": "complete", **result.as_dict()}
        )
        return result
    except Exception as exc:
        failure = (
            exc
            if isinstance(exc, GuardedRestoreError)
            else GuardedRestoreError(f"Startup recovery failed: {exc}")
        )
        if activated and destination is not None and destination.exists():
            try:
                os.replace(destination, failed_path)
            except OSError:
                pass
        try:
            _write_json(
                journal_path,
                {
                    "schema": 1,
                    "phase": "failed",
                    "error": str(failure),
                    "unverified_recovery_copy": (
                        str(failed_path) if failed_path.exists() else ""
                    ),
                    "completed_utc": now_iso(),
                },
            )
        except OSError:
            pass
        if failure is exc:
            raise
        raise failure from exc
    finally:
        stage_path.unlink(missing_ok=True)
        if lock_fd is not None:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)
