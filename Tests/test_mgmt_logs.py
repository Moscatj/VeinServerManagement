from __future__ import annotations

import json
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
