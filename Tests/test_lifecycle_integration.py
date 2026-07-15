from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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
import start_server  # noqa: E402
from GUI.dashboard_state import should_autostart_log_monitor  # noqa: E402
from Tools import monitors  # noqa: E402


WORKER = ROOT / "Tests" / "fixtures" / "fake_lifecycle_worker.py"


def _wait_until(predicate, *, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise AssertionError("Timed out waiting for isolated lifecycle state")


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


class _ControlledProcess:
    def __init__(
        self,
        process: subprocess.Popen[bytes],
        command_name: str,
        required_stop_flag: Path | None = None,
    ) -> None:
        self.process = process
        self.pid = process.pid
        self.info = {"pid": process.pid, "cmdline": [sys.executable, command_name]}
        self.required_stop_flag = required_stop_flag

    def terminate(self) -> None:
        if self.required_stop_flag is not None and not self.required_stop_flag.is_file():
            raise AssertionError("Monitor termination happened before its stop flag")
        self.process.terminate()

    def wait(self, timeout: int | None = None) -> None:
        self.process.wait(timeout=timeout)


class LifecycleIntegrationTests(unittest.TestCase):
    def test_start_joinable_and_controlled_stop_leave_terminal_state(self) -> None:
        children: list[subprocess.Popen[bytes]] = []
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            runtime = base / "Runtime"
            server_root = base / "Server"
            game_log = server_root / "Vein" / "Saved" / "Logs" / "Vein.log"
            selected_exe = server_root / "Vein" / "Binaries" / "Win64" / "VeinServer-Win64-Test.exe"
            selected_exe.parent.mkdir(parents=True)
            selected_exe.write_bytes(b"test fixture placeholder")
            runtime.mkdir()

            def launch(role: str) -> subprocess.Popen[bytes]:
                process = subprocess.Popen(
                    [sys.executable, str(WORKER), "--role", role, "--runtime", str(runtime), "--game-log", str(game_log)],
                    cwd=ROOT,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                children.append(process)
                return process

            server: subprocess.Popen[bytes] | None = None
            log_monitor: subprocess.Popen[bytes] | None = None
            crash_monitor: subprocess.Popen[bytes] | None = None

            def write_server_state(running: bool, pid: int = 0, **extra: object) -> None:
                payload: dict[str, object] = {
                    "status": "running" if running else "stopped",
                    "process_running": running,
                    "pid": pid,
                    **extra,
                }
                (runtime / "server_state.json").write_text(json.dumps(payload), encoding="utf-8")

            def start_monitors() -> list[str]:
                nonlocal log_monitor, crash_monitor
                log_monitor = launch("log")
                crash_monitor = launch("crash")
                _wait_until(lambda: (runtime / "log_monitor.pid").is_file())
                _wait_until(lambda: (runtime / "crash_monitor.pid").is_file())
                return ["log", "crash"]

            def start_fake_server(**_kwargs: object) -> subprocess.Popen[bytes]:
                nonlocal server
                server = launch("server")
                return server

            vcfg = SimpleNamespace(
                server_dir=server_root,
                runtime_dir=runtime,
                selected_exe=selected_exe,
                server_executables=[str(selected_exe.relative_to(server_root))],
                raw={"monitor": {"startup_quiet_seconds": 0}},
            )

            try:
                with mock.patch.object(start_server, "load_and_validate_config", return_value=vcfg), mock.patch.object(
                    start_server, "find_running_server", return_value=None
                ), mock.patch.object(start_server, "_steam_update_if_enabled"), mock.patch.object(
                    start_server, "_start_monitors", side_effect=start_monitors
                ), mock.patch.object(start_server, "start_vein_server", side_effect=start_fake_server), mock.patch.object(
                    start_server, "send_discord_message"
                ), mock.patch.object(start_server, "RUNTIME_DIR", runtime), mock.patch.object(
                    start_server, "PID_SERVER", runtime / "server.pid"
                ), mock.patch.object(start_server, "RESTARTING_LOCK", runtime / "restarting.lock"), mock.patch.object(
                    start_server,
                    "create_startup_lock",
                    side_effect=lambda: (runtime / "startup_in_progress.lock").write_text("starting", encoding="utf-8"),
                ), mock.patch.object(
                    start_server,
                    "clear_startup_lock",
                    side_effect=lambda: (runtime / "startup_in_progress.lock").unlink(missing_ok=True),
                ), mock.patch.object(start_server, "set_server_state", side_effect=write_server_state), mock.patch.object(
                    start_server, "set_autorestart_quiet_period"
                ):
                    self.assertEqual(start_server.main(), 0)

                assert server is not None and log_monitor is not None and crash_monitor is not None
                _wait_until(lambda: _read_json(runtime / "log_monitor.state.json").get("server_joinable") is True)
                self.assertIsNone(server.poll())
                self.assertIsNone(log_monitor.poll())
                self.assertIsNone(crash_monitor.poll())
                self.assertFalse((runtime / "startup_in_progress.lock").exists())

                log_process = _ControlledProcess(log_monitor, "monitor_log.py", runtime / "stop_log_monitor.flag")
                crash_process = _ControlledProcess(crash_monitor, "crash_monitor.py", runtime / "stop_crash_monitor.flag")
                server_process = _ControlledProcess(server, "fake_server.py")
                recovery_suppressed: list[bool] = []

                def stop_fake_server() -> None:
                    self.assertIsNotNone(log_monitor.poll())
                    self.assertIsNotNone(crash_monitor.poll())
                    recovery_suppressed.append(
                        not should_autostart_log_monitor(
                            server_running=True,
                            monitor_enabled=True,
                            monitor_running=False,
                            manual_stop=(runtime / "stop_log_monitor.flag").is_file(),
                            lifecycle_busy=False,
                            shutdown_in_progress=(runtime / "shutdown_in_progress.flag").is_file(),
                        )
                    )
                    server_process.terminate()
                    server_process.wait(timeout=3)

                def begin_shutdown(window_sec: int = 180) -> None:
                    del window_sec
                    (runtime / "shutdown_in_progress.flag").write_text("intentional", encoding="utf-8")

                with mock.patch.object(
                    monitors.psutil, "process_iter", return_value=[log_process, crash_process, server_process]
                ), mock.patch.object(shutdown_server, "RUNTIME_DIR", runtime), mock.patch.object(
                    shutdown_server, "PID_SERVER", runtime / "server.pid"
                ), mock.patch.object(shutdown_server, "PRE_SHUTDOWN_WARN", 0), mock.patch.object(
                    shutdown_server, "config", {"shutdown_quiet_seconds": 0}
                ), mock.patch.object(
                    shutdown_server, "begin_intentional_shutdown", side_effect=begin_shutdown
                ), mock.patch.object(
                    shutdown_server,
                    "end_intentional_shutdown",
                    side_effect=lambda: (runtime / "shutdown_in_progress.flag").unlink(missing_ok=True),
                ), mock.patch.object(
                    shutdown_server,
                    "clear_flag",
                    side_effect=lambda: (runtime / "server_running.flag").unlink(missing_ok=True),
                ), mock.patch.object(shutdown_server, "set_server_state", side_effect=write_server_state), mock.patch.object(
                    shutdown_server, "list_all_vein_server_procs", return_value=[SimpleNamespace(pid=server.pid)]
                ), mock.patch.object(
                    shutdown_server, "stop_all_vein_processes_aggressive", side_effect=stop_fake_server
                ), mock.patch.object(shutdown_server, "is_feature_enabled", return_value=False), mock.patch.object(
                    shutdown_server, "send_discord_message"
                ), mock.patch.object(shutdown_server, "_stop_py_process") as fallback_stop, mock.patch.object(
                    shutdown_server, "_clear_locks"
                ):
                    shutdown_server.main()

                fallback_stop.assert_not_called()
                self.assertEqual(recovery_suppressed, [True])
                self.assertTrue((runtime / "stop_log_monitor.flag").is_file())
                self.assertTrue((runtime / "stop_crash_monitor.flag").is_file())
                self.assertFalse((runtime / "shutdown_in_progress.flag").exists())
                for name in ("server.pid", "log_monitor.pid", "crash_monitor.pid"):
                    self.assertFalse((runtime / name).exists())

                server_state = _read_json(runtime / "server_state.json")
                log_state = _read_json(runtime / "log_monitor.state.json")
                crash_state = _read_json(runtime / "crash_monitor.state.json")
                self.assertEqual(server_state.get("status"), "stopped")
                self.assertFalse(log_state.get("active"))
                self.assertFalse(log_state.get("server_joinable"))
                self.assertEqual(log_state.get("status"), "stopped")
                self.assertFalse(crash_state.get("active"))
                self.assertEqual(crash_state.get("mode"), "stopped")
            finally:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
