from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.backup_pins import pin_backup  # noqa: E402
from Tools.backup_restore_preview import inspect_restore_archive  # noqa: E402


class BackupRestorePreviewTests(unittest.TestCase):
    def _archive(
        self, root: Path, *, payload: bytes = b"save data", declared_sha: str = ""
    ) -> Path:
        archive = root / "backup.zip"
        manifest = {
            "reason": "Manual",
            "created_utc": "2026-07-23T12:00:00Z",
            "save_filename": "Server.vns",
            "bytes": len(payload),
            "sha256": declared_sha or hashlib.sha256(payload).hexdigest(),
            "version": 1,
        }
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("Server.vns", payload)
            bundle.writestr("manifest.json", json.dumps(manifest))
        return archive

    def test_valid_preview_is_read_only_and_reports_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root)
            save_dir = root / "live"
            save_dir.mkdir()
            live = save_dir / "Server.vns"
            live.write_bytes(b"current")
            before = archive.read_bytes()
            pin_backup(archive, label="Before migration", note="Known good")

            preview = inspect_restore_archive(
                archive, save_dir=save_dir, server_running=False
            )

            self.assertEqual(archive.read_bytes(), before)
            self.assertTrue(preview.archive_valid)
            self.assertTrue(preview.manifest_valid)
            self.assertTrue(preview.ready_for_guarded_restore)
            self.assertEqual(preview.save_member, "Server.vns")
            self.assertEqual(preview.destination, str(live))
            self.assertTrue(preview.destination_exists)
            self.assertEqual(preview.restore_point_label, "Before migration")

    def test_running_server_blocks_readiness_without_invalidating_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = inspect_restore_archive(
                self._archive(root), save_dir=root / "live", server_running=True
            )

            self.assertTrue(preview.archive_valid)
            self.assertFalse(preview.ready_for_guarded_restore)
            self.assertIn("Stop the server", preview.warnings[0])

    def test_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, declared_sha="0" * 64)

            preview = inspect_restore_archive(
                archive, save_dir=root / "live", server_running=False
            )

            self.assertFalse(preview.archive_valid)
            self.assertFalse(preview.ready_for_guarded_restore)
            self.assertTrue(any("hash" in error.lower() for error in preview.errors))

    def test_unsafe_member_and_missing_manifest_are_not_restore_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../Server.vns", b"save")

            preview = inspect_restore_archive(
                archive, save_dir=root / "live", server_running=False
            )

            self.assertFalse(preview.archive_valid)
            self.assertFalse(preview.manifest_valid)
            self.assertTrue(any("unsafe path" in error.lower() for error in preview.errors))
            self.assertTrue(any("manifest is missing" in warning.lower() for warning in preview.warnings))


if __name__ == "__main__":
    unittest.main()
