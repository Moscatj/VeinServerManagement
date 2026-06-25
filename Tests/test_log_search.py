from __future__ import annotations

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

from Tools import log_search  # noqa: E402


class LogSearchTests(unittest.TestCase):
    def test_parse_since_supports_seconds_and_units(self) -> None:
        with mock.patch.object(log_search.time, "time", return_value=1_000.0):
            self.assertEqual(log_search.parse_since("30"), 970.0)
            self.assertEqual(log_search.parse_since("2m"), 880.0)
            self.assertEqual(log_search.parse_since("1.5h"), 1_000.0 - 5_400.0)
            self.assertIsNone(log_search.parse_since("all"))
            self.assertIsNone(log_search.parse_since("not-a-window"))

    def test_search_logs_filters_pattern_case_and_limit(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_path = Path(tmp) / "monitor.log"
            log_path.write_text(
                "INFO startup\nERROR failed first\nwarning low disk\nERROR failed second\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                log_search.mgmt_logs,
                "iter_log_files",
                return_value=iter([log_path]),
            ), mock.patch.object(
                log_search.mgmt_logs,
                "is_archived_path",
                return_value=False,
            ):
                hits = log_search.search_logs(
                    subsystems=["monitor_log"],
                    pattern="error",
                    case_sensitive=False,
                    max_hits=1,
                )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].subsystem, "monitor_log")
        self.assertEqual(hits[0].line_no, 2)
        self.assertEqual(hits[0].text, "ERROR failed first")

    def test_search_logs_honors_since_timestamp(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            old_log = Path(tmp) / "old.log"
            new_log = Path(tmp) / "new.log"
            old_log.write_text("ERROR old\n", encoding="utf-8")
            new_log.write_text("ERROR new\n", encoding="utf-8")
            old_mtime = time.time() - 500
            new_mtime = time.time()
            old_log.touch()
            new_log.touch()
            import os

            os.utime(old_log, (old_mtime, old_mtime))
            os.utime(new_log, (new_mtime, new_mtime))
            with mock.patch.object(
                log_search.mgmt_logs,
                "iter_log_files",
                return_value=iter([old_log, new_log]),
            ), mock.patch.object(
                log_search.mgmt_logs,
                "is_archived_path",
                return_value=False,
            ):
                hits = log_search.search_logs(
                    subsystems=["monitor_log"],
                    pattern="ERROR",
                    since_ts=time.time() - 60,
                )

        self.assertEqual([hit.text for hit in hits], ["ERROR new"])


if __name__ == "__main__":
    unittest.main()
