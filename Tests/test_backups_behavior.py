from __future__ import annotations

import json
import os
import sys
import time
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import backups  # noqa: E402


class BackupsBehaviorTests(unittest.TestCase):
    def _cfg(self, base: Path, *, enabled: bool = True) -> dict:
        return {
            "backups": {
                "enable": enabled,
                "root": str(base / "Backups"),
                "folders": {"Manual": "Manual", "Crash": "Crash"},
                "retention": {
                    "default": {"max_backups": 10, "max_age_days": 30},
                    "Manual": {"max_backups": 1, "max_age_days": 30},
                },
                "save_dir": str(base / "Saved"),
                "save_filenames": ["Server.vns"],
                "discord": {"notify_on_create": False, "notify_on_prune": False},
            },
            "features": {"enable_backups": enabled},
            "runtime_dir": str(base / "Runtime"),
            "log_backup_root": str(base / "LogBackups"),
            "log_backup_max_files": 1,
            "log_backup_max_age_days": 30,
        }

    def test_make_backup_creates_zip_manifest_and_state(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save_dir = base / "Saved"
            save_dir.mkdir()
            save = save_dir / "Server.vns"
            save.write_bytes(b"save-data")
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch("builtins.print"):
                created = backups.make_backup("Manual")

            self.assertIsNotNone(created)
            self.assertTrue(created.exists())
            with zipfile.ZipFile(created, "r") as zf:
                self.assertIn("Server.vns", zf.namelist())
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            state = json.loads((base / "Runtime" / "backup.state.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["reason"], "Manual")
        self.assertEqual(manifest["save_filename"], "Server.vns")
        self.assertEqual(state["last_reason"], "Manual")
        self.assertEqual(state["counts"]["TOTAL"], 1)

    def test_make_backup_raises_skip_when_disabled(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base, enabled=False)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch("builtins.print"):
                with self.assertRaises(backups.BackupSkip):
                    backups.make_backup("Manual")

    def test_prune_backups_deletes_oldest_over_count(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            old_zip = folder / "old.zip"
            new_zip = folder / "new.zip"
            old_zip.write_text("old", encoding="utf-8")
            new_zip.write_text("new", encoding="utf-8")
            old_ts = time.time() - 100
            new_ts = time.time()
            os.utime(old_zip, (old_ts, old_ts))
            os.utime(new_zip, (new_ts, new_ts))
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result, {"deleted": 1})
            self.assertFalse(old_zip.exists())
            self.assertTrue(new_zip.exists())

    def test_latest_backup_searches_folders_and_restore_extracts_target(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save_dir = base / "Saved"
            backup_dir = base / "Backups" / "Manual"
            backup_dir.mkdir(parents=True)
            archive = backup_dir / "backup.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("nested/Server.vns", "restored")
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch("builtins.print"):
                latest = backups.latest_backup()
                restored = backups.restore_from_latest("Server.vns")
                restored_text = (save_dir / "nested" / "Server.vns").read_text(encoding="utf-8")

            self.assertEqual(latest, archive)
            self.assertTrue(restored)
            self.assertEqual(restored_text, "restored")

    def test_export_log_snapshot_zips_copy_and_prunes(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            log = base / "Vein.log"
            log.write_text("line\n", encoding="utf-8")
            old = base / "LogBackups" / "old.log.zip"
            old.parent.mkdir()
            old.write_text("old", encoding="utf-8")
            os.utime(old, (time.time() - 100, time.time() - 100))
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ):
                zipped = backups.export_log_snapshot(log, label="manual")

            self.assertIsNotNone(zipped)
            self.assertTrue(zipped.exists())
            self.assertFalse(old.exists())
            with zipfile.ZipFile(zipped, "r") as zf:
                self.assertEqual(zf.read(zf.namelist()[0]).decode("utf-8").splitlines(), ["line"])


if __name__ == "__main__":
    unittest.main()
