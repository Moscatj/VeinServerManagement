from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import mgmt_logs  # noqa: E402


class MgmtLogsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory(dir=ROOT)
        self.root = Path(self.tmp.name) / "Logs"
        self.archive = self.root / "Archive"
        self.root.mkdir()
        self.archive.mkdir()
        self.originals = {
            "ROOT": mgmt_logs.ROOT,
            "ARCHIVE": mgmt_logs.ARCHIVE,
            "ARCHIVE_ROOT": mgmt_logs.ARCHIVE_ROOT,
            "LAYOUT": dict(mgmt_logs.LAYOUT),
            "_MANIFEST_FILE": mgmt_logs._MANIFEST_FILE,
            "RETENTION": dict(mgmt_logs.RETENTION),
        }
        mgmt_logs.ROOT = self.root
        mgmt_logs.ARCHIVE = {
            "enabled": True,
            "root": self.archive,
            "max_files": 200,
            "max_age_days": 90,
        }
        mgmt_logs.ARCHIVE_ROOT = self.archive
        mgmt_logs.LAYOUT = {"vein_manager": "gui", "monitor_log": "monitors/log_monitor"}
        mgmt_logs._MANIFEST_FILE = self.root / "manifest.json"
        mgmt_logs.RETENTION = {
            "max_files": 50,
            "max_age_days": 90,
            "per_subsystem": {},
        }

    def tearDown(self) -> None:
        for key, value in self.originals.items():
            setattr(mgmt_logs, key, value)
        self.tmp.cleanup()

    def test_allocate_stream_files_records_latest_and_manifest(self) -> None:
        streams = mgmt_logs.allocate_stream_files(
            "vein_manager",
            label="startup",
            streams=("stdout", "stderr"),
            metadata={"action": "test"},
        )
        for path in streams.values():
            path.write_text("", encoding="utf-8")

        self.assertEqual(set(streams), {"stdout", "stderr"})
        self.assertTrue(streams["stdout"].parent.samefile(self.root / "gui"))
        self.assertEqual(mgmt_logs.latest_log_path("vein_manager", "stdout"), streams["stdout"])
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("vein_manager", manifest)
        self.assertEqual(manifest["vein_manager"][0]["label"], "startup")
        self.assertEqual(manifest["vein_manager"][0]["metadata"]["action"], "test")

    def test_archive_logs_moves_inactive_files(self) -> None:
        path = mgmt_logs.subsystem_dir("vein_manager") / "old.log"
        path.write_text("old\n", encoding="utf-8")

        moved = mgmt_logs.archive_logs("vein_manager", include_active=True)

        self.assertEqual(len(moved), 1)
        source, dest = moved[0]
        self.assertEqual(source, path)
        self.assertFalse(path.exists())
        self.assertTrue(dest.exists())
        self.assertTrue(mgmt_logs.is_archived_path(dest))

    def test_migrate_legacy_logs_dry_run_does_not_move_files(self) -> None:
        legacy = self.root / "server.stdout.log"
        legacy.write_text("legacy\n", encoding="utf-8")

        moves = mgmt_logs.migrate_legacy_logs(dry_run=True)

        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0][0], legacy)
        self.assertTrue(legacy.exists())

    def test_latest_log_path_falls_back_to_newest_matching_stream(self) -> None:
        subdir = mgmt_logs.subsystem_dir("vein_manager")
        old = subdir / "old.stdout.log"
        new = subdir / "new.stdout.log"
        stderr = subdir / "new.stderr.log"
        old.write_text("old\n", encoding="utf-8")
        new.write_text("new\n", encoding="utf-8")
        stderr.write_text("err\n", encoding="utf-8")
        old_time = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(old, (old_time, old_time))

        self.assertEqual(mgmt_logs.latest_log_path("vein_manager", "stdout"), new)
        self.assertEqual(mgmt_logs.latest_log_path("vein_manager", None), stderr)
        self.assertEqual(mgmt_logs.latest_log_file("vein_manager"), stderr)

    def test_allocate_log_file_supports_empty_stream_and_manifest_filtering(self) -> None:
        path = mgmt_logs.allocate_log_file(
            "custom name",
            label="single",
            stream=None,
            timestamped=False,
            metadata={"one": 1},
        )
        path.write_text("", encoding="utf-8")

        self.assertEqual(path.name, "single.stdout.log")
        self.assertTrue(path.parent.samefile(self.root / "custom_name"))
        self.assertEqual(list(mgmt_logs.manifest("custom name")), ["custom_name"])
        self.assertEqual(mgmt_logs.latest_log_path("custom name"), path)

    def test_retention_archives_excess_logs_but_keeps_latest_active_file(self) -> None:
        mgmt_logs.RETENTION = {
            "max_files": 1,
            "max_age_days": 90,
            "per_subsystem": {},
        }
        active = mgmt_logs.allocate_log_file(
            "vein_manager",
            label="active",
            stream="stdout",
            timestamped=False,
        )
        active.write_text("active\n", encoding="utf-8")

        subdir = mgmt_logs.subsystem_dir("vein_manager")
        keep = subdir / "keep.stdout.log"
        old = subdir / "old.stdout.log"
        keep.write_text("keep\n", encoding="utf-8")
        old.write_text("old\n", encoding="utf-8")
        old_time = (datetime.now() - timedelta(days=2)).timestamp()
        os.utime(old, (old_time, old_time))

        mgmt_logs._apply_retention("vein_manager")

        self.assertTrue(active.exists())
        self.assertTrue(keep.exists())
        self.assertFalse(old.exists())
        self.assertTrue((self.archive / "gui" / "old.stdout.log").exists())

    def test_archive_disabled_leaves_live_logs_in_place(self) -> None:
        mgmt_logs.ARCHIVE = {
            "enabled": False,
            "root": self.archive,
            "max_files": 200,
            "max_age_days": 90,
        }
        path = mgmt_logs.subsystem_dir("vein_manager") / "live.log"
        path.write_text("live\n", encoding="utf-8")

        self.assertEqual(mgmt_logs.archive_logs("vein_manager", include_active=True), [])
        self.assertTrue(path.exists())

    def test_migrate_legacy_logs_moves_files_and_records_manifest(self) -> None:
        legacy = self.root / "server.stdout.log"
        legacy.write_text("legacy\n", encoding="utf-8")
        existing = mgmt_logs.subsystem_dir("start_server") / "server.stdout.log"
        existing.write_text("existing\n", encoding="utf-8")

        moves = mgmt_logs.migrate_legacy_logs()

        self.assertEqual(len(moves), 1)
        source, dest = moves[0]
        self.assertEqual(source, legacy)
        self.assertFalse(legacy.exists())
        self.assertTrue(dest.exists())
        self.assertEqual(dest.name, "server.stdout.1.log")
        manifest = mgmt_logs.manifest("start_server")["start_server"]
        self.assertEqual(
            manifest[0]["streams"]["stdout"].replace("\\", "/"),
            "start_server/server.stdout.1.log",
        )
        self.assertTrue(manifest[0]["metadata"]["migrated"])

    def test_archive_all_logs_collects_known_subsystems(self) -> None:
        one = mgmt_logs.subsystem_dir("vein_manager") / "one.log"
        two = mgmt_logs.subsystem_dir("monitor_log") / "two.log"
        one.write_text("one\n", encoding="utf-8")
        two.write_text("two\n", encoding="utf-8")

        moved = mgmt_logs.archive_all_logs(include_active=True)

        self.assertEqual({src.name for src, _ in moved}, {"one.log", "two.log"})
        self.assertTrue((self.archive / "gui" / "one.log").exists())
        self.assertTrue((self.archive / "monitors" / "log_monitor" / "two.log").exists())

    def test_available_subsystems_does_not_treat_archive_as_subsystem(self) -> None:
        archived = self.archive / "gui" / "old.log"
        archived.parent.mkdir(parents=True)
        archived.write_text("old\n", encoding="utf-8")

        subsystems = mgmt_logs.available_subsystems(include_empty=True)

        self.assertIn("vein_manager", subsystems)
        self.assertNotIn("archive", subsystems)

    def test_archive_all_logs_does_not_rearchive_archive_folder(self) -> None:
        archived = self.archive / "gui" / "old.log"
        archived.parent.mkdir(parents=True)
        archived.write_text("old\n", encoding="utf-8")

        moved = mgmt_logs.archive_all_logs(include_active=True)

        self.assertEqual(moved, [])
        self.assertTrue(archived.exists())
        self.assertFalse((self.archive / "Archive").exists())


if __name__ == "__main__":
    unittest.main()
