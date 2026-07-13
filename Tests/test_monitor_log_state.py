from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

import monitor_log  # noqa: E402


class MonitorLogStateTests(unittest.TestCase):
    def test_state_explains_waiting_path_on_clean_install(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            state = runtime / "log_monitor.state.json"
            expected = runtime / "Server" / "Vein" / "Saved" / "Logs" / "Vein.log"
            runtime_paths = {
                "runtime": runtime,
                "state_log": state,
                "pid_log": runtime / "log_monitor.pid",
                "stop_log": runtime / "stop_log_monitor.flag",
            }
            with mock.patch.object(monitor_log, "_runtime_paths", return_value=runtime_paths), mock.patch.object(
                monitor_log,
                "log_file_candidates",
                return_value=[expected],
            ):
                monitor_log._write_logmon_state(
                    active=True,
                    tailing_file=None,
                    watching_server=True,
                    status="waiting_for_log",
                    message=f"Waiting for game log: {expected}",
                )

            payload = json.loads(state.read_text(encoding="utf-8"))

        self.assertTrue(payload["active"])
        self.assertEqual(payload["status"], "waiting_for_log")
        self.assertEqual(payload["expected_log_files"], [str(expected)])
        self.assertIn(str(expected), payload["message"])


if __name__ == "__main__":
    unittest.main()
