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

from Tools import runtime  # noqa: E402


class RuntimeHelperTests(unittest.TestCase):
    def test_flag_read_write_clear_roundtrip(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            flag = Path(tmp) / "server_running.flag"
            with mock.patch.object(runtime, "STATE_FLAG", flag):
                runtime.write_flag(123, "server.exe", "/Game/Map")
                data = runtime.read_flag()
                runtime.clear_flag()

        self.assertEqual(data["pid"], 123)
        self.assertEqual(data["exe"], "server.exe")
        self.assertFalse(flag.exists())

    def test_shutdown_and_quiet_flags(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            shutdown = Path(tmp) / "shutdown.flag"
            quiet = Path(tmp) / "quiet.until"
            with mock.patch.object(runtime, "SHUTDOWN_FLAG", shutdown), mock.patch.object(
                runtime,
                "QUIET_UNTIL",
                quiet,
            ), mock.patch.object(runtime, "_now", return_value=100.0):
                runtime.begin_intentional_shutdown(window_sec=30)
                self.assertTrue(runtime.is_shutdown_in_progress(max_age_seconds=900))
                self.assertTrue(runtime.autorestart_quiet_active())
                runtime.end_intentional_shutdown()

        self.assertFalse(shutdown.exists())

    def test_startup_lock_helpers(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            lock = Path(tmp) / "startup.lock"
            with mock.patch.object(runtime, "STARTUP_LOCK", lock), mock.patch.object(
                runtime,
                "_now",
                return_value=100.0,
            ):
                runtime.create_startup_lock()
                self.assertTrue(runtime.startup_grace_active(max_age_seconds=180))
                runtime.clear_startup_lock()

        self.assertFalse(lock.exists())

    def test_set_server_state_sanitizes_extra_values(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            state_path = Path(tmp) / "server_state.json"
            with mock.patch.object(runtime, "SERVER_STATE", state_path):
                runtime.set_server_state(True, pid=321, extra_path=Path("abc"))
                data = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(data["status"], "running")
        self.assertEqual(data["pid"], 321)
        self.assertEqual(data["extra_path"], "abc")


if __name__ == "__main__":
    unittest.main()
