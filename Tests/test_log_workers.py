from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from GUI.logs import ArchiveLogsWorker, FileTail, LogErrorWorker, LogSearchWorker  # noqa: E402


class LogWorkerTests(unittest.TestCase):
    def test_file_tail_attaches_when_clean_server_creates_first_log(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_file = Path(tmp) / "Server" / "Vein" / "Saved" / "Logs" / "Vein.log"
            chunks: list[str] = []
            tail = FileTail(lambda: log_file)
            tail.chunk.connect(chunks.append)
            tail.start()
            try:
                log_file.parent.mkdir(parents=True)
                log_file.write_text("first startup line\n", encoding="utf-8")
                tail.poll()
            finally:
                tail.stop()

        self.assertEqual("".join(chunks).splitlines(), ["first startup line"])

    def test_file_tail_reopens_truncated_log(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_file = Path(tmp) / "Vein.log"
            log_file.write_text("old startup content\n", encoding="utf-8")
            chunks: list[str] = []
            tail = FileTail(lambda: log_file)
            tail.chunk.connect(chunks.append)
            tail.start()
            try:
                with log_file.open("a", encoding="utf-8") as stream:
                    stream.write("new line\n")
                tail.poll()
                log_file.write_text("reset\n", encoding="utf-8")
                tail.poll()
            finally:
                tail.stop()

        self.assertEqual("".join(chunks).splitlines(), ["new line", "reset"])

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
