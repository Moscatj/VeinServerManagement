from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from GUI.logs import ArchiveLogsWorker, LogErrorWorker, LogSearchWorker  # noqa: E402


class LogWorkerTests(unittest.TestCase):
    def test_log_search_worker_emits_payload(self) -> None:
        hit = mock.Mock(subsystem="gui", file=Path("app.log"), line_no=3, text="ERROR")
        worker = LogSearchWorker(
            subsystems=["gui"],
            pattern="ERROR",
            since="1h",
            limit=5,
            case_sensitive=True,
            include_archive=False,
        )
        payloads: list[list[dict]] = []
        worker.signals.ready.connect(payloads.append)
        with mock.patch("GUI.logs.log_search.parse_since", return_value=123.0), mock.patch(
            "GUI.logs.log_search.search_logs",
            return_value=[hit],
        ):
            worker.run()

        self.assertEqual(payloads, [[{"subsystem": "gui", "file": "app.log", "line": 3, "text": "ERROR"}]])

    def test_log_error_worker_emits_relative_events(self) -> None:
        root = ROOT / "Logs"
        event = mock.Mock(
            file=root / "gui" / "app.log",
            line_no=4,
            level="ERROR",
            message="failed",
            timestamp=10.0,
        )
        worker = LogErrorWorker(subsystems=["gui"], since=None, limit=10)
        payloads: list[list[dict]] = []
        worker.signals.ready.connect(payloads.append)
        with mock.patch("GUI.logs.mgmt_logs.management_log_root", return_value=root), mock.patch(
            "GUI.logs.log_search.parse_since",
            return_value=None,
        ), mock.patch(
            "GUI.logs.log_events.collect_recent_events",
            return_value=[event],
        ):
            worker.run()

        self.assertEqual(payloads[0][0]["subsystem"], "gui")
        self.assertEqual(payloads[0][0]["file"], str(Path("gui") / "app.log"))
        self.assertEqual(payloads[0][0]["line"], 4)

    def test_archive_logs_worker_emits_moved_files(self) -> None:
        moved = [(Path("old.log"), Path("Archive/old.log"))]
        worker = ArchiveLogsWorker(include_active=True)
        payloads: list[list[tuple[Path, Path]]] = []
        worker.signals.ready.connect(payloads.append)
        with mock.patch("GUI.logs.mgmt_logs.archive_all_logs", return_value=moved) as archive:
            worker.run()

        archive.assert_called_once_with(include_active=True)
        self.assertEqual(payloads, [moved])


if __name__ == "__main__":
    unittest.main()
