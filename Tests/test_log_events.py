from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import log_events  # noqa: E402


class LogEventsTests(unittest.TestCase):
    def test_scan_file_detects_levels_and_limit(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "server.log"
            path.write_text(
                "INFO booted\nWARNING retrying\nERROR failed\nfatal error happened\n",
                encoding="utf-8",
            )

            events = log_events.scan_file(path, limit=2)

        self.assertEqual([event.level for event in events], ["WARNING", "ERROR"])
        self.assertEqual(events[0].line_no, 2)
        self.assertEqual(events[1].message, "ERROR failed")

    def test_scan_file_missing_returns_empty(self) -> None:
        events = log_events.scan_file(ROOT / "missing-test-log.log")

        self.assertEqual(events, [])

    def test_collect_recent_events_filters_archive_and_sorts(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            live = base / "live.log"
            archived = base / "archived.log"
            live.write_text("ERROR live\n", encoding="utf-8")
            archived.write_text("ERROR archived\n", encoding="utf-8")
            old_ts = time.time() - 500
            new_ts = time.time()
            os.utime(live, (new_ts, new_ts))
            os.utime(archived, (old_ts, old_ts))

            with mock.patch.object(
                log_events.mgmt_logs,
                "iter_log_files",
                side_effect=lambda *_, **__: iter([archived, live]),
            ), mock.patch.object(
                log_events.mgmt_logs,
                "is_archived_path",
                side_effect=lambda p: Path(p) == archived,
            ):
                live_only = log_events.collect_recent_events(
                    ["monitor_log"], include_archive=False
                )
                archive_only = log_events.collect_recent_events(
                    ["monitor_log"], include_archive=True, archive_only=True
                )
                recent = log_events.collect_recent_events(
                    ["monitor_log"], include_archive=True, since_ts=time.time() - 60
                )

        self.assertEqual([event.message for event in live_only], ["ERROR live"])
        self.assertEqual([event.message for event in archive_only], ["ERROR archived"])
        self.assertEqual([event.message for event in recent], ["ERROR live"])


if __name__ == "__main__":
    unittest.main()
