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
from Tools.backup_pins import pin_backup, pin_sidecar_path  # noqa: E402


class BackupsBehaviorTests(unittest.TestCase):
    def test_manual_backup_main_reports_success_skip_and_failure(self) -> None:
        created = Path("Backups/Manual/example.zip")
        with mock.patch.object(backups, "make_backup", return_value=created), mock.patch(
            "builtins.print"
        ) as printer:
            success = backups.manual_backup_main()
        self.assertEqual(success, 0)
        self.assertIn("Backup created", printer.call_args.args[0])

        with mock.patch.object(
            backups, "make_backup", side_effect=backups.BackupSkip("disabled")
        ), mock.patch("builtins.print") as printer:
            skipped = backups.manual_backup_main()
        self.assertEqual(skipped, 2)
        self.assertIn("Backup skipped", printer.call_args.args[0])

        with mock.patch.object(
            backups, "make_backup", side_effect=backups.BackupError("disk full")
        ), mock.patch("builtins.print") as printer:
            failed = backups.manual_backup_main()
        self.assertEqual(failed, 1)
        self.assertIn("Backup failed", printer.call_args.args[0])

    def _cfg(self, base: Path, *, enabled: bool = True) -> dict:
        return {
            "backups": {
                "enable": enabled,
                "root": str(base / "Backups"),
                "folders": {"Manual": "Manual", "Crash": "Crash"},
                "retention": {
                    "default": {
                        "minimum_backups": 3,
                        "max_backups": 10,
                        "max_age_days": 30,
                    },
                    "Manual": {
                        "minimum_backups": 1,
                        "max_backups": 1,
                        "max_age_days": 30,
                    },
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

    def test_feature_gate_honors_primary_enabled_key_and_legacy_enable_key(self) -> None:
        with mock.patch.object(
            backups, "_cfg", return_value={"backups": {"enabled": False}}
        ):
            self.assertFalse(backups._feature_enabled())
        with mock.patch.object(
            backups, "_cfg", return_value={"backups": {"enable": False}}
        ):
            self.assertFalse(backups._feature_enabled())
        with mock.patch.object(
            backups,
            "_cfg",
            return_value={"backups": {"enabled": True, "enable": False}},
        ):
            self.assertTrue(backups._feature_enabled())

    def test_make_backup_raises_skip_when_save_is_missing(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch("builtins.print"):
                with self.assertRaises(backups.BackupSkip):
                    backups.make_backup("Manual")

    def test_make_backup_wraps_destination_creation_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save = base / "Saved" / "Server.vns"
            save.parent.mkdir()
            save.write_text("save", encoding="utf-8")
            blocked_dest = base / "blocked"
            blocked_dest.write_text("not a directory", encoding="utf-8")

            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch("builtins.print"):
                with self.assertRaises(backups.BackupError):
                    backups.make_backup("Manual", dst=blocked_dest / "child")

    def test_make_backup_includes_extra_files_and_ignores_missing_extras(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save = base / "Saved" / "Server.vns"
            extra = base / "extra.txt"
            save.parent.mkdir()
            save.write_text("save", encoding="utf-8")
            extra.write_text("extra", encoding="utf-8")

            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch("builtins.print"):
                created = backups.make_backup("Manual", files=[save, extra, base / "missing.txt"])

            with zipfile.ZipFile(created, "r") as zf:
                names = set(zf.namelist())

        self.assertIn("Server.vns", names)
        self.assertIn("extra/extra.txt", names)
        self.assertNotIn("extra/Server.vns", names)
        self.assertNotIn("extra/missing.txt", names)

    def test_make_backup_wraps_archive_write_failure_and_removes_temp_copy(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save = base / "Saved" / "Server.vns"
            save.parent.mkdir()
            save.write_text("save", encoding="utf-8")
            dest = base / "Backups" / "Manual"

            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=False,
            ), mock.patch.object(
                backups.zipfile,
                "ZipFile",
                side_effect=OSError("zip failed"),
            ), mock.patch.object(backups, "prune_backups") as prune, mock.patch(
                "builtins.print"
            ):
                with self.assertRaises(backups.BackupError):
                    backups.make_backup("Manual")

            leftovers = list(dest.glob(".tmp_copy_*"))

        self.assertEqual(leftovers, [])
        prune.assert_not_called()

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

    def test_prune_backups_excludes_pins_from_cleanup_and_unpinned_quota(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["retention"]["Manual"] = {
                "enabled": True,
                "by_count": True,
                "by_age": True,
                "minimum_backups": 1,
                "max_backups": 2,
                "max_age_days": 1,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            archives = []
            for index in range(4):
                archive = folder / f"backup-{index}.zip"
                archive.write_bytes(str(index).encode())
                old = time.time() - ((10 - index) * 86400)
                os.utime(archive, (old, old))
                archives.append(archive)
            pin_backup(archives[0], label="Known good")

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups, "is_discord_channel_enabled", return_value=False
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result["deleted"], 2)
            self.assertTrue(archives[0].exists())
            self.assertTrue(pin_sidecar_path(archives[0]).exists())
            self.assertFalse(archives[1].exists())
            self.assertFalse(archives[2].exists())
            self.assertTrue(archives[3].exists())

    def test_prune_backups_deletes_by_age_and_notifies_when_enabled(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["discord"]["notify_on_prune"] = True
            cfg["backups"]["retention"]["Manual"] = {
                "minimum_backups": 1,
                "max_backups": 10,
                "max_age_days": 0,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            old_zip = folder / "old.zip"
            newest_zip = folder / "newest.zip"
            old_zip.write_text("old", encoding="utf-8")
            newest_zip.write_text("new", encoding="utf-8")
            old_ts = time.time() - 86400 * 2
            os.utime(old_zip, (old_ts, old_ts))

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=True,
            ), mock.patch.object(backups, "send_discord_message") as discord:
                result = backups.prune_backups("Manual")
            old_exists = old_zip.exists()
            newest_exists = newest_zip.exists()

        self.assertEqual(result, {"deleted": 1})
        self.assertFalse(old_exists)
        self.assertTrue(newest_exists)
        discord.assert_called_once()

    def test_prune_backups_can_be_disabled_without_deleting_archives(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["retention"]["Manual"] = {
                "enabled": False,
                "by_count": True,
                "by_age": True,
                "max_backups": 1,
                "max_age_days": 1,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            for name in ("old-a.zip", "old-b.zip"):
                archive = folder / name
                archive.write_text(name, encoding="utf-8")
                old_ts = time.time() - 86400 * 10
                os.utime(archive, (old_ts, old_ts))

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups, "is_discord_channel_enabled", return_value=False
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result, {"deleted": 0})
            self.assertEqual(len(list(folder.glob("*.zip"))), 2)

    def test_prune_backups_applies_only_selected_cleanup_rule(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["retention"]["Manual"] = {
                "enabled": True,
                "by_count": False,
                "by_age": True,
                "max_backups": 1,
                "max_age_days": 30,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            for name in ("new-a.zip", "new-b.zip"):
                (folder / name).write_text(name, encoding="utf-8")

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups, "is_discord_channel_enabled", return_value=False
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result, {"deleted": 0})
            self.assertEqual(len(list(folder.glob("*.zip"))), 2)

    def test_prune_backups_can_disable_age_rule_independently(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["retention"]["Manual"] = {
                "enabled": True,
                "by_count": True,
                "by_age": False,
                "max_backups": 10,
                "max_age_days": 1,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            archive = folder / "old.zip"
            archive.write_text("old", encoding="utf-8")
            old_ts = time.time() - 86400 * 10
            os.utime(archive, (old_ts, old_ts))

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups, "is_discord_channel_enabled", return_value=False
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result, {"deleted": 0})
            self.assertTrue(archive.exists())

    def test_age_cleanup_preserves_minimum_rollback_points_after_long_downtime(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = self._cfg(base)
            cfg["backups"]["retention"]["Manual"] = {
                "enabled": True,
                "by_count": True,
                "by_age": True,
                "minimum_backups": 3,
                "max_backups": 10,
                "max_age_days": 30,
            }
            folder = base / "Backups" / "Manual"
            folder.mkdir(parents=True)
            archives = []
            now = time.time()
            for index in range(4):
                archive = folder / f"backup-{index}.zip"
                archive.write_text(str(index), encoding="utf-8")
                timestamp = now - 86400 * (60 - index)
                os.utime(archive, (timestamp, timestamp))
                archives.append(archive)

            with mock.patch.object(backups, "_cfg", return_value=cfg), mock.patch.object(
                backups, "is_discord_channel_enabled", return_value=False
            ):
                result = backups.prune_backups("Manual")

            self.assertEqual(result, {"deleted": 1})
            self.assertFalse(archives[0].exists())
            self.assertTrue(all(archive.exists() for archive in archives[1:]))

    def test_latest_backup_searches_folders_and_legacy_restore_never_writes(self) -> None:
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

            self.assertEqual(latest, archive)
            self.assertFalse(restored)
            self.assertFalse(save_dir.exists())

    def test_legacy_restore_is_disabled_without_opening_archive(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            backup_dir = base / "Backups" / "Manual"
            backup_dir.mkdir(parents=True)
            archive = backup_dir / "backup.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Other.vns", "other")

            with mock.patch.object(
                backups.zipfile,
                "ZipFile",
                side_effect=OSError("bad zip"),
            ) as open_zip, mock.patch("builtins.print"):
                self.assertFalse(backups.restore_from_latest("Server.vns"))
            open_zip.assert_not_called()

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

    def test_export_log_snapshot_handles_missing_source_and_copy_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            missing = base / "missing.log"
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)):
                self.assertIsNone(backups.export_log_snapshot(missing))

            src = base / "Vein.log"
            src.write_text("line", encoding="utf-8")
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups.shutil,
                "copy2",
                side_effect=OSError("copy failed"),
            ), mock.patch("builtins.print") as printed:
                self.assertIsNone(backups.export_log_snapshot(src))

        printed.assert_called_once()

    def test_export_log_snapshot_sends_discord_breadcrumb_when_enabled(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            src = base / "Vein.log"
            src.write_text("line", encoding="utf-8")
            with mock.patch.object(backups, "_cfg", return_value=self._cfg(base)), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=True,
            ), mock.patch.object(backups, "send_discord_message") as discord:
                self.assertIsNotNone(backups.export_log_snapshot(src))

        discord.assert_called_once()


if __name__ == "__main__":
    unittest.main()
