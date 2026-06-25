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

    def test_read_flag_missing_and_invalid_returns_none(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            flag = Path(tmp) / "server_running.flag"
            with mock.patch.object(runtime, "STATE_FLAG", flag):
                self.assertIsNone(runtime.read_flag())
                flag.write_text("{invalid", encoding="utf-8")
                with mock.patch("builtins.print") as printed:
                    self.assertIsNone(runtime.read_flag())

        printed.assert_called_once()

    def test_clear_runtime_markers_removes_state_pid_and_flag(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            flag = base / "server_running.flag"
            pid = base / "server.pid"
            state = base / "server_state.json"
            for path in (flag, pid, state):
                path.write_text("x", encoding="utf-8")

            with mock.patch.object(runtime, "STATE_FLAG", flag), mock.patch.object(
                runtime,
                "PID_SERVER",
                pid,
            ), mock.patch.object(runtime, "SERVER_STATE", state):
                runtime.clear_runtime_markers()

        self.assertFalse(flag.exists())
        self.assertFalse(pid.exists())
        self.assertFalse(state.exists())

    def test_stale_and_invalid_runtime_windows_are_inactive(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            startup = base / "startup.lock"
            shutdown = base / "shutdown.flag"
            quiet = base / "quiet.until"
            startup.write_text("1", encoding="utf-8")
            shutdown.write_text("1", encoding="utf-8")
            quiet.write_text("not-an-int", encoding="utf-8")

            with mock.patch.object(runtime, "STARTUP_LOCK", startup), mock.patch.object(
                runtime,
                "SHUTDOWN_FLAG",
                shutdown,
            ), mock.patch.object(runtime, "QUIET_UNTIL", quiet), mock.patch.object(
                runtime,
                "_now",
                return_value=startup.stat().st_mtime + 1000,
            ):
                self.assertFalse(runtime.startup_grace_active(max_age_seconds=10))
                self.assertFalse(runtime.is_shutdown_in_progress(max_age_seconds=10))
                self.assertFalse(runtime.autorestart_quiet_active())

    def test_set_server_state_falls_back_when_state_writer_fails(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            state_path = Path(tmp) / "server_state.json"
            with mock.patch.object(runtime, "SERVER_STATE", state_path), mock.patch.object(
                runtime,
                "_write_server_state",
                side_effect=RuntimeError("boom"),
            ):
                runtime.set_server_state(False, pid=0, reason=Path("manual"))
                data = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertFalse(data["process_running"])
        self.assertEqual(data["pid"], 0)
        self.assertEqual(data["reason"], "manual")


if __name__ == "__main__":
    unittest.main()
