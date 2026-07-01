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

    def test_resolve_runtime_dir_uses_config_or_project_fallback(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            configured = Path(tmp) / "Runtime"
            with mock.patch.object(runtime, "get_path", return_value=str(configured)):
                self.assertEqual(runtime._resolve_runtime_dir(), configured)

            with mock.patch.object(runtime, "get_path", return_value=""):
                self.assertEqual(runtime._resolve_runtime_dir(), runtime.PROJECT_ROOT / "Runtime")

    def test_atomic_write_json_writes_payload_and_swallows_replace_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "Runtime" / "state.json"
            runtime._atomic_write_json(path, {"ok": True})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"ok": True})

            failing = Path(tmp) / "Runtime" / "failing.json"
            with mock.patch.object(runtime.os, "replace", side_effect=OSError("replace failed")):
                runtime._atomic_write_json(failing, {"ok": False})

        self.assertFalse(failing.exists())

    def test_flag_helpers_report_write_and_clear_failures(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            flag = Path(tmp) / "server_running.flag"
            with mock.patch.object(runtime, "STATE_FLAG", flag), mock.patch.object(
                Path,
                "write_text",
                side_effect=OSError("cannot write"),
            ), mock.patch("builtins.print") as printed:
                runtime.write_flag(1, "server.exe", "/Game")

            printed.assert_called_once()

            with mock.patch.object(runtime, "STATE_FLAG", flag), mock.patch.object(
                Path,
                "unlink",
                side_effect=OSError("cannot unlink"),
            ), mock.patch("builtins.print") as printed:
                runtime.clear_flag()

            printed.assert_called_once()

    def test_shutdown_startup_and_pid_clear_helpers_swallow_filesystem_errors(self) -> None:
        bad_path = mock.Mock()
        bad_path.write_text.side_effect = OSError("cannot write")
        bad_path.unlink.side_effect = OSError("cannot unlink")

        with mock.patch.object(runtime, "SHUTDOWN_FLAG", bad_path), mock.patch.object(
            runtime,
            "set_autorestart_quiet_period",
        ) as quiet:
            runtime.begin_intentional_shutdown(window_sec=-5)
            quiet.assert_called_once_with(0)
            runtime.end_intentional_shutdown()

        with mock.patch.object(runtime, "STARTUP_LOCK", bad_path):
            runtime.create_startup_lock()
            runtime.clear_startup_lock()

        with mock.patch.object(runtime, "PID_SERVER", bad_path):
            runtime.clear_pid_file()

    def test_runtime_window_helpers_return_false_on_stat_or_read_errors(self) -> None:
        bad_shutdown = mock.Mock()
        bad_shutdown.exists.return_value = True
        bad_shutdown.stat.side_effect = OSError("no stat")
        with mock.patch.object(runtime, "SHUTDOWN_FLAG", bad_shutdown):
            self.assertFalse(runtime.is_shutdown_in_progress())

        bad_startup = mock.Mock()
        bad_startup.exists.return_value = True
        bad_startup.stat.side_effect = OSError("no stat")
        with mock.patch.object(runtime, "STARTUP_LOCK", bad_startup):
            self.assertFalse(runtime.startup_grace_active())

        bad_quiet = mock.Mock()
        bad_quiet.exists.return_value = True
        bad_quiet.read_text.side_effect = OSError("cannot read")
        with mock.patch.object(runtime, "QUIET_UNTIL", bad_quiet):
            self.assertFalse(runtime.autorestart_quiet_active())

    def test_quiet_period_handles_negative_seconds_and_expiration(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            quiet = Path(tmp) / "quiet.until"
            with mock.patch.object(runtime, "QUIET_UNTIL", quiet), mock.patch.object(
                runtime,
                "_now",
                return_value=100.0,
            ):
                runtime.set_autorestart_quiet_period(seconds=-10)
                self.assertFalse(runtime.autorestart_quiet_active())

                runtime.set_autorestart_quiet_period(seconds=50)
                self.assertTrue(runtime.autorestart_quiet_active())

            with mock.patch.object(runtime, "QUIET_UNTIL", quiet), mock.patch.object(
                runtime,
                "_now",
                return_value=200.0,
            ):
                self.assertFalse(runtime.autorestart_quiet_active())

    def test_set_server_state_swallows_primary_and_fallback_failures(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            state_path = Path(tmp) / "server_state.json"
            with mock.patch.object(runtime, "SERVER_STATE", state_path), mock.patch.object(
                runtime,
                "_write_server_state",
                side_effect=RuntimeError("primary failed"),
            ), mock.patch.object(
                runtime,
                "_atomic_write_json",
                side_effect=RuntimeError("fallback failed"),
            ):
                runtime.set_server_state(True, pid=1)

        self.assertFalse(state_path.exists())

    def test_clear_runtime_markers_swallows_state_delete_failure(self) -> None:
        state = mock.Mock()
        state.unlink.side_effect = OSError("cannot unlink")
        with mock.patch.object(runtime, "clear_flag") as clear_flag, mock.patch.object(
            runtime,
            "clear_pid_file",
        ) as clear_pid, mock.patch.object(runtime, "SERVER_STATE", state):
            runtime.clear_runtime_markers()

        clear_flag.assert_called_once()
        clear_pid.assert_called_once()


if __name__ == "__main__":
    unittest.main()
