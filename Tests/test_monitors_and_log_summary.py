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

import log_summary  # noqa: E402
import crash_monitor  # noqa: E402
from Tools import log_events, monitors  # noqa: E402


class FakeMonitorProcess:
    def __init__(self, cmdline: list[str] | None = None) -> None:
        self.info = {"cmdline": cmdline or []}
        self.terminated = False
        self.wait_timeout: int | None = None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int | None = None) -> None:
        self.wait_timeout = timeout


class MonitorStopTests(unittest.TestCase):
    def test_request_monitor_stop_flags_asserts_both_until_next_start(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            paths = monitors.request_monitor_stop_flags(Path(tmp))

            self.assertEqual(len(paths), 2)
            self.assertTrue(all(path.is_file() for path in paths))
            self.assertIn("intentional shutdown", paths[0].read_text(encoding="utf-8"))

    def test_mark_monitor_stopped_clears_stale_state_and_pid(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            (runtime / "crash_monitor.state.json").write_text(
                '{"active": true, "mode": "idle", "watching_server": true}',
                encoding="utf-8",
            )
            (runtime / "crash_monitor.pid").write_text("123", encoding="utf-8")

            state_path = monitors.mark_monitor_stopped(runtime, "crash")
            payload = json.loads(state_path.read_text(encoding="utf-8"))

            self.assertFalse(payload["active"])
            self.assertFalse(payload["watching_server"])
            self.assertEqual(payload["mode"], "stopped")
            self.assertFalse((runtime / "crash_monitor.pid").exists())

    def test_stop_processes_terminates_matching_cmdline_processes(self) -> None:
        match = FakeMonitorProcess(["python", "Controller/monitor_log.py"])
        miss = FakeMonitorProcess(["python", "Controller/crash_monitor.py"])

        with mock.patch.object(monitors.psutil, "process_iter", return_value=[match, miss]):
            stopped = monitors.stop_log_monitor()

        self.assertTrue(stopped)
        self.assertTrue(match.terminated)
        self.assertEqual(match.wait_timeout, 5)
        self.assertFalse(miss.terminated)

    def test_stop_processes_ignores_wait_errors_and_process_access_errors(self) -> None:
        match = FakeMonitorProcess(["python", "monitor_log.py"])
        match.wait = mock.Mock(side_effect=TimeoutError("still stopping"))
        denied = mock.Mock()
        denied.info = {"cmdline": ["python", "monitor_log.py"]}
        denied.terminate.side_effect = monitors.psutil.AccessDenied(pid=123)

        with mock.patch.object(monitors.psutil, "process_iter", return_value=[match, denied]):
            stopped = monitors.stop_log_monitor()

        self.assertFalse(stopped)
        self.assertTrue(match.terminated)
        denied.terminate.assert_called_once()

    def test_stop_processes_tolerates_outer_process_iter_failure(self) -> None:
        with mock.patch.object(monitors.psutil, "process_iter", side_effect=RuntimeError("psutil failed")):
            self.assertFalse(monitors.stop_crash_monitor())

    def test_stop_processes_matches_packaged_monitor_subcommand(self) -> None:
        packaged = FakeMonitorProcess(
            ["VeinTools.exe", "monitor-log", "--config", "config.yaml"]
        )

        with mock.patch.object(monitors.psutil, "process_iter", return_value=[packaged]):
            monitors.stop_log_monitor()

        self.assertTrue(packaged.terminated)
        self.assertEqual(packaged.wait_timeout, 5)

    def test_stop_all_monitors_delegates_to_both_monitor_stoppers(self) -> None:
        with mock.patch.object(monitors, "stop_log_monitor") as stop_log, mock.patch.object(
            monitors, "stop_crash_monitor"
        ) as stop_crash:
            monitors.stop_all_monitors()

        stop_log.assert_called_once()
        stop_crash.assert_called_once()


class CrashMonitorLoopTests(unittest.TestCase):
    def test_stop_request_records_terminal_state_and_cleans_runtime_markers(self) -> None:
        with mock.patch.object(
            crash_monitor, "is_feature_enabled", return_value=True
        ), mock.patch.object(
            crash_monitor, "_stop_requested", return_value=True
        ), mock.patch.object(crash_monitor, "_send") as send, mock.patch.object(
            crash_monitor, "_write_pid"
        ) as write_pid, mock.patch.object(
            crash_monitor, "_write_state_mode"
        ) as write_state, mock.patch.object(
            crash_monitor, "_clear_pid_and_stopflag"
        ) as clear:
            crash_monitor.main()

        write_pid.assert_called_once_with()
        send.assert_any_call("🛑 Crash monitor stop requested; exiting.")
        write_state.assert_any_call("stopped", active=False, watching=False)
        clear.assert_called_once_with()

    def test_intentional_shutdown_never_enters_restart_path(self) -> None:
        with mock.patch.object(
            crash_monitor, "is_feature_enabled", return_value=True
        ), mock.patch.object(
            crash_monitor, "_stop_requested", side_effect=[False, True]
        ), mock.patch.object(
            crash_monitor, "is_shutdown_in_progress", return_value=True
        ), mock.patch.object(crash_monitor.time, "sleep"), mock.patch.object(
            crash_monitor, "_write_state_mode"
        ) as write_state, mock.patch.object(
            crash_monitor, "initiate_controlled_restart"
        ) as restart, mock.patch.object(
            crash_monitor, "_send"
        ), mock.patch.object(
            crash_monitor, "_write_pid"
        ), mock.patch.object(
            crash_monitor, "_clear_pid_and_stopflag"
        ):
            crash_monitor.main()

        write_state.assert_any_call(
            "intentional_shutdown", active=True, watching=False
        )
        restart.assert_not_called()

    def test_startup_grace_suppresses_crash_restart_after_confirmed_misses(self) -> None:
        running_flag = mock.Mock()
        running_flag.exists.return_value = True
        with mock.patch.object(
            crash_monitor, "is_feature_enabled", return_value=True
        ), mock.patch.object(
            crash_monitor, "_stop_requested", side_effect=[False, False, True]
        ), mock.patch.object(
            crash_monitor, "is_shutdown_in_progress", return_value=False
        ), mock.patch.object(
            crash_monitor, "_breaker_active", return_value=False
        ), mock.patch.object(
            crash_monitor, "STATE_FLAG", running_flag
        ), mock.patch.object(
            crash_monitor, "is_server_running", return_value=False
        ), mock.patch.object(
            crash_monitor, "_running_server_exists", return_value=False
        ), mock.patch.object(
            crash_monitor, "startup_grace_active", return_value=True
        ), mock.patch.object(crash_monitor.time, "sleep"), mock.patch.object(
            crash_monitor, "initiate_controlled_restart"
        ) as restart, mock.patch.object(
            crash_monitor, "_debounced_crash_notify"
        ) as notify, mock.patch.object(
            crash_monitor, "_send"
        ), mock.patch.object(
            crash_monitor, "_write_pid"
        ), mock.patch.object(
            crash_monitor, "_write_state_mode"
        ), mock.patch.object(
            crash_monitor, "_clear_pid_and_stopflag"
        ):
            crash_monitor.main()

        notify.assert_not_called()
        restart.assert_not_called()

    def test_confirmed_crash_requests_only_one_controlled_restart(self) -> None:
        running_flag = mock.Mock()
        running_flag.exists.return_value = True
        with mock.patch.object(
            crash_monitor, "is_feature_enabled", return_value=True
        ), mock.patch.object(
            crash_monitor, "_stop_requested", side_effect=[False, False, True]
        ), mock.patch.object(
            crash_monitor, "is_shutdown_in_progress", return_value=False
        ), mock.patch.object(
            crash_monitor, "_breaker_active", return_value=False
        ), mock.patch.object(
            crash_monitor, "STATE_FLAG", running_flag
        ), mock.patch.object(
            crash_monitor, "is_server_running", return_value=False
        ), mock.patch.object(
            crash_monitor, "_running_server_exists", return_value=False
        ), mock.patch.object(
            crash_monitor, "startup_grace_active", return_value=False
        ), mock.patch.object(
            crash_monitor, "autorestart_quiet_active", return_value=False
        ), mock.patch.object(
            crash_monitor, "_count_attempts_in_window", return_value=0
        ), mock.patch.object(crash_monitor.time, "sleep"), mock.patch.object(
            crash_monitor, "initiate_controlled_restart", return_value=True
        ) as restart, mock.patch.object(
            crash_monitor, "_debounced_crash_notify"
        ) as notify, mock.patch.object(
            crash_monitor, "_append_attempt"
        ) as append, mock.patch.object(
            crash_monitor, "_send"
        ), mock.patch.object(
            crash_monitor, "_write_pid"
        ), mock.patch.object(
            crash_monitor, "_write_state_mode"
        ), mock.patch.object(
            crash_monitor, "_clear_pid_and_stopflag"
        ):
            crash_monitor.main()

        notify.assert_called_once()
        restart.assert_called_once_with(reason="proc_missing")
        append.assert_called_once()


class LogSummaryTests(unittest.TestCase):
    def test_serialize_events_uses_relative_management_log_paths(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Logs"
            event_file = root / "monitor_log" / "latest.stdout.log"
            event_file.parent.mkdir(parents=True)
            event = log_events.LogEvent(event_file, 7, "ERROR", "failed startup", 1.0)

            with mock.patch.object(log_summary.mgmt_logs, "management_log_root", return_value=root):
                payload = log_summary._serialize_events([event])

        self.assertEqual(
            payload,
            [
                {
                    "file": str(Path("monitor_log") / "latest.stdout.log"),
                    "line": 7,
                    "level": "ERROR",
                    "message": "failed startup",
                }
            ],
        )

    def test_summarize_subsystem_collects_events_and_writes_summary_json(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Logs"
            subsystem_dir = root / "monitor_log"
            event_file = subsystem_dir / "latest.stdout.log"
            event_file.parent.mkdir(parents=True)
            event = log_events.LogEvent(event_file, 3, "WARNING", "timeout", 2.0)

            with mock.patch.object(
                log_summary.log_events,
                "collect_recent_events",
                return_value=[event],
            ) as collect, mock.patch.object(
                log_summary.mgmt_logs,
                "management_log_root",
                return_value=root,
            ), mock.patch.object(
                log_summary.mgmt_logs,
                "subsystem_dir",
                return_value=subsystem_dir,
            ):
                payload = log_summary.summarize_subsystem("monitor_log", limit=5, per_file=2)

            written = json.loads((subsystem_dir / "summary.json").read_text(encoding="utf-8"))

        collect.assert_called_once_with(
            ["monitor_log"], since_ts=None, per_file_limit=2, max_events=5
        )
        self.assertEqual(payload["subsystem"], "monitor_log")
        self.assertEqual(written["events"][0]["message"], "timeout")

    def test_summarize_subsystem_returns_payload_when_write_fails(self) -> None:
        event = log_events.LogEvent(Path("not-under-root.log"), 1, "ERROR", "boom", 1.0)
        bad_dest = mock.Mock()
        bad_dest.__truediv__ = mock.Mock(return_value=bad_dest)
        bad_dest.write_text.side_effect = OSError("cannot write")

        with mock.patch.object(log_summary.log_events, "collect_recent_events", return_value=[event]), mock.patch.object(
            log_summary.mgmt_logs,
            "management_log_root",
            return_value=Path("Logs"),
        ), mock.patch.object(log_summary.mgmt_logs, "subsystem_dir", return_value=bad_dest):
            payload = log_summary.summarize_subsystem("crash_monitor", limit=1, per_file=1)

        self.assertEqual(payload["events"][0]["file"], "not-under-root.log")

    def test_main_writes_combined_summary_for_default_subsystems(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Logs"
            root.mkdir()

            with mock.patch.object(
                log_summary.mgmt_logs,
                "available_subsystems",
                return_value=["monitor_log", "crash_monitor"],
            ), mock.patch.object(
                log_summary,
                "summarize_subsystem",
                side_effect=lambda subsystem, limit, per_file: {
                    "subsystem": subsystem,
                    "limit": limit,
                    "per_file": per_file,
                },
            ) as summarize, mock.patch.object(
                log_summary.mgmt_logs,
                "management_log_root",
                return_value=root,
            ), mock.patch.object(
                sys,
                "argv",
                ["log_summary.py", "--limit", "9", "--per-file", "4"],
            ), mock.patch(
                "builtins.print"
            ) as printed:
                result = log_summary.main()

            combined = json.loads((root / "summary.json").read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(summarize.call_count, 2)
        self.assertEqual(combined["summaries"]["monitor_log"]["limit"], 9)
        self.assertEqual(combined["summaries"]["crash_monitor"]["per_file"], 4)
        printed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
