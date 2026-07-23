from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.backup_pins import (  # noqa: E402
    BackupPinError,
    is_archive_pinned,
    pin_backup,
    pin_sidecar_path,
    read_backup_pin,
    remove_backup_pin,
    update_backup_pin,
)


class BackupPinTests(unittest.TestCase):
    def test_pin_metadata_is_atomic_readable_and_does_not_modify_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "backup.zip"
            archive.write_bytes(b"immutable archive")
            before = archive.read_bytes()

            pin = pin_backup(archive, label=" Before update ", note="Known good state")

            self.assertEqual(archive.read_bytes(), before)
            self.assertTrue(is_archive_pinned(archive))
            self.assertEqual(pin.label, "Before update")
            self.assertEqual(read_backup_pin(archive), pin)
            payload = json.loads(pin_sidecar_path(archive).read_text(encoding="utf-8"))
            self.assertEqual(payload["archive"], archive.name)
            self.assertEqual(len(payload["archive_sha256"]), 64)

    def test_malformed_pin_metadata_remains_cleanup_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "backup.zip"
            archive.write_bytes(b"archive")
            pin_sidecar_path(archive).write_text("not json", encoding="utf-8")

            pin = read_backup_pin(archive)

            self.assertTrue(is_archive_pinned(archive))
            self.assertIsNotNone(pin)
            self.assertEqual(pin.status, "invalid")

    def test_pin_requires_existing_zip_and_bounded_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "backup.zip"
            archive.write_bytes(b"archive")
            with self.assertRaises(BackupPinError):
                pin_backup(archive, label="")
            with self.assertRaises(BackupPinError):
                pin_backup(Path(tmp) / "missing.zip", label="Point")
            with self.assertRaises(BackupPinError):
                pin_backup(archive, label="x" * 81)

    def test_update_and_remove_protection_never_modify_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "backup.zip"
            archive.write_bytes(b"immutable archive")
            before = archive.read_bytes()
            original = pin_backup(archive, label="First", note="Original")

            updated = update_backup_pin(archive, label="Branch point", note="Revised")

            self.assertEqual(updated.label, "Branch point")
            self.assertEqual(updated.note, "Revised")
            self.assertEqual(updated.pinned_utc, original.pinned_utc)
            self.assertEqual(archive.read_bytes(), before)
            self.assertTrue(remove_backup_pin(archive))
            self.assertEqual(archive.read_bytes(), before)
            self.assertFalse(is_archive_pinned(archive))

    def test_update_and_remove_require_existing_restore_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "backup.zip"
            archive.write_bytes(b"archive")
            with self.assertRaises(BackupPinError):
                update_backup_pin(archive, label="Updated")
            with self.assertRaises(BackupPinError):
                remove_backup_pin(archive)


if __name__ == "__main__":
    unittest.main()
