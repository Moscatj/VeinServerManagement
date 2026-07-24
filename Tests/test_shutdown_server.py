from __future__ import annotations

from contextlib import contextmanager
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

os.environ.setdefault("VEIN_CONFIG", str(ROOT / "Config" / "config.example.yaml"))
os.environ.setdefault("VEIN_DISABLE_DISCORD", "1")

import shutdown_server  # noqa: E402


class ShutdownServerTests(unittest.TestCase):
    @contextmanager
    def _normal_shutdown_context(
        self,
        runtime: Path,
        *,
        log_stopped: bool = True,
        crash_stopped: bool = True,
        backups_enabled: bool = True,
        shutdown_backup_enabled: bool = True,
        backup_result=None,
        backup_error: Exception | None = None,
    ):
        pid_file = runtime / "server.pid"
        pid_file.write_text("123", encoding="utf-8")
        with mock.patch.object(
            shutdown_server, "RUNTIME_DIR", runtime
        ), mock.patch.object(
            shutdown_server, "PID_SERVER", pid_file
        ), mock.patch.object(
            shutdown_server, "PRE_SHUTDOWN_WARN", 0
        ), mock.patch.object(
            shutdown_server, "config", {"shutdown_quiet_seconds": 0}
        ), mock.patch.object(
            shutdown_server, "begin_intentional_shutdown"
        ) as begin, mock.patch.object(
            shutdown_server, "clear_flag"
        ) as clear_flag, mock.patch.object(
            shutdown_server, "set_server_state"
        ) as set_state, mock.patch.object(
            shutdown_server, "request_monitor_stop_flags"
        ) as request_flags, mock.patch.object(
            shutdown_server, "stop_log_monitor", return_value=log_stopped
        ) as stop_log, mock.patch.object(
            shutdown_server, "stop_crash_monitor", return_value=crash_stopped
        ) as stop_crash, mock.patch.object(
            shutdown_server, "mark_monitor_stopped"
        ) as mark_stopped, mock.patch.object(
            shutdown_server, "_stop_py_process"
        ) as fallback_stop, mock.patch.object(
            shutdown_server, "list_all_vein_server_procs", return_value=[]
        ), mock.patch.object(
            shutdown_server, "stop_all_vein_processes_aggressive"
        ) as stop_servers, mock.patch.object(
            shutdown_server, "backups_enabled", return_value=backups_enabled
        ), mock.patch.object(
            shutdown_server,
            "backup_trigger_enabled",
            return_value=shutdown_backup_enabled,
        ), mock.patch.object(
            shutdown_server,
            "backup_save_file",
            return_value=backup_result,
            side_effect=backup_error,
        ) as backup, mock.patch.object(
            shutdown_server, "send_discord_message"
        ) as send:
            yield SimpleNamespace(
                begin=begin,
                clear_flag=clear_flag,
                set_state=set_state,
                request_flags=request_flags,
                stop_log=stop_log,
                stop_crash=stop_crash,
                mark_stopped=mark_stopped,
                fallback_stop=fallback_stop,
                stop_servers=stop_servers,
                backup=backup,
                send=send,
                pid_file=pid_file,
            )

    def test_disabled_backup_and_partial_monitor_stop_still_stop_server(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            with self._normal_shutdown_context(
                runtime,
                log_stopped=False,
                crash_stopped=True,
                backups_enabled=False,
            ) as calls:
                shutdown_server._normal_shutdown()

        calls.begin.assert_called_once_with(window_sec=0)
        calls.request_flags.assert_called_once_with(runtime)
        calls.fallback_stop.assert_called_once_with("monitor_log.py")
        calls.mark_stopped.assert_called_once_with(runtime, "crash")
        calls.stop_servers.assert_called_once_with()
        calls.backup.assert_not_called()
        self.assertFalse(calls.pid_file.exists())
        final_message = calls.send.call_args_list[-1].args[0]
        self.assertIn("disabled by backup policy", final_message)

    def test_successful_shutdown_backup_is_announced(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            archive = runtime / "Backups" / "Shutdown.zip"
            with self._normal_shutdown_context(
                runtime,
                backup_result=archive,
            ) as calls:
                shutdown_server._normal_shutdown()

        calls.backup.assert_called_once_with(reason="Shutdown")
        self.assertEqual(
            calls.mark_stopped.call_args_list,
            [mock.call(runtime, "log"), mock.call(runtime, "crash")],
        )
        self.assertIn("Shutdown.zip", calls.send.call_args_list[-1].args[0])

    def test_backup_failure_does_not_hide_completed_shutdown(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            with self._normal_shutdown_context(
                runtime,
                backup_error=RuntimeError("backup unavailable"),
            ) as calls, mock.patch("builtins.print") as printed:
                shutdown_server._normal_shutdown()

        calls.stop_servers.assert_called_once_with()
        self.assertTrue(
            any("Backup failed" in str(call.args[0]) for call in printed.call_args_list)
        )
        self.assertIn("Backup skipped or failed", calls.send.call_args_list[-1].args[0])

    def test_main_always_clears_locks_and_intentional_shutdown_marker(self) -> None:
        with mock.patch.object(
            shutdown_server, "_normal_shutdown", side_effect=RuntimeError("stop failed")
        ), mock.patch.object(
            shutdown_server, "_clear_locks"
        ) as clear_locks, mock.patch.object(
            shutdown_server, "end_intentional_shutdown"
        ) as end_shutdown, mock.patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "stop failed"):
                shutdown_server.main()

        clear_locks.assert_called_once_with()
        end_shutdown.assert_called_once_with()

    def test_warning_countdown_sends_initial_and_final_notice_without_blocking(self) -> None:
        with mock.patch.object(
            shutdown_server, "COUNTDOWN_FINAL_WARNING_AT", 2
        ), mock.patch.object(
            shutdown_server, "send_discord_message"
        ) as send, mock.patch.object(shutdown_server.time, "sleep") as sleep:
            shutdown_server._warn_and_wait(3)

        self.assertEqual(sleep.call_count, 3)
        self.assertEqual(send.call_count, 2)
        self.assertIn("3 seconds", send.call_args_list[0].args[0])
        self.assertIn("2 seconds", send.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
