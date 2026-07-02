"""
Process control helpers for Vein Manager GUI.

This controller centralizes start/stop logic for the server and monitors so the
Main window can delegate without carrying the implementation details.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, Optional

from PySide6 import QtCore

from Tools import mgmt_logs


class RunOnceWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        finished = QtCore.Signal(int, str, str)
        failed = QtCore.Signal(str)

    def __init__(
        self,
        run_once: Callable[..., tuple[int, str, str]],
        command: str,
        *,
        cwd: Path,
        timeout: int,
    ) -> None:
        super().__init__()
        self._run_once = run_once
        self._command = command
        self._cwd = cwd
        self._timeout = timeout
        self.signals = self.Signals()

    def run(self) -> None:
        try:
            code, out, err = self._run_once(
                self._command,
                cwd=self._cwd,
                timeout=self._timeout,
            )
            self.signals.finished.emit(int(code), str(out or ""), str(err or ""))
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class StopMonitorWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        status = QtCore.Signal(str)

    def __init__(
        self,
        *,
        monitor_name: str,
        pid_file: Path,
        wait_for_monitor_exit: Callable[[Path, int], bool],
        fallback_command: str,
        fallback_cwd: Path,
        run_once: Callable[..., tuple[int, str, str]],
        initial_timeout: int,
        fallback_timeout: int = 10,
    ) -> None:
        super().__init__()
        self.monitor_name = monitor_name
        self.pid_file = pid_file
        self.wait_for_monitor_exit = wait_for_monitor_exit
        self.fallback_command = fallback_command
        self.fallback_cwd = fallback_cwd
        self.run_once = run_once
        self.initial_timeout = initial_timeout
        self.fallback_timeout = fallback_timeout
        self.signals = self.Signals()

    def run(self) -> None:
        if self.wait_for_monitor_exit(self.pid_file, timeout_sec=self.initial_timeout):
            self.signals.status.emit(f"{self.monitor_name} stopped.")
            return
        try:
            self.run_once(
                self.fallback_command,
                self.fallback_cwd,
                timeout=self.fallback_timeout,
            )
        except Exception:
            pass
        if not self.wait_for_monitor_exit(self.pid_file, timeout_sec=self.fallback_timeout):
            self.signals.status.emit(
                f"{self.monitor_name} stop requested; process still running."
            )
            return
        self.signals.status.emit(f"{self.monitor_name} stop requested.")


class ProcessController:
    def __init__(
        self,
        owner,
        *,
        pyexe: Callable[[], str],
        resolved_paths: Callable[[], Dict[str, Path]],
        rt_paths: Callable[[str], dict],
        runtime_paths: Callable[[str], dict],
        spawn_logged: Callable[..., object],
        run_once: Callable[..., tuple[int, str, str]],
        mkflag: Callable[[Path], None],
        rm: Callable[[Path], None],
        wait_for_monitor_exit: Callable[[Path, int], bool],
        ctrl_dir: Path,
    ) -> None:
        self.owner = owner
        self._pyexe = pyexe
        self._resolved_paths = resolved_paths
        self._rt_paths = rt_paths
        self._runtime_paths = runtime_paths
        self._spawn_logged = spawn_logged
        self._run_once = run_once
        self._mkflag = mkflag
        self._rm = rm
        self._wait_for_monitor_exit = wait_for_monitor_exit
        self._ctrl_dir = ctrl_dir
        self._pool = QtCore.QThreadPool.globalInstance()
        self._workers: list[QtCore.QRunnable] = []

    # ------------------------ Server / monitors -------------------------------
    def start_server(self) -> None:
        paths = self._resolved_paths()
        py = paths["start_server"]
        if not py.exists():
            self.owner._status("start_server.py not found.")
            return
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.owner.config_path
        srv_stdout = mgmt_logs.allocate_log_file(
            "vein_manager",
            label="start_server",
            record_latest=False,
            metadata={"action": "start_server", "config": self.owner.config_path},
        )
        try:
            self._spawn_logged(f'{self._pyexe()} "{py}"', srv_stdout, py.parent, env=env)
            self.owner._status("Server starting.")
        except Exception as e:
            self.owner._status(f"Start failed: {e}")

    def stop_server(self, *, after_success: Optional[Callable[[], None]] = None) -> None:
        paths = self._resolved_paths()
        py = paths["shutdown_server"]
        if not py.exists():
            self.owner._status("shutdown_server.py not found.")
            return
        worker = RunOnceWorker(
            self._run_once,
            f'{self._pyexe()} "{py}"',
            cwd=py.parent,
            timeout=180,
        )
        self._workers.append(worker)

        def finished(code: int, out: str, err: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            if out:
                self.owner._write_action_log("stop_server", "stdout", out)
            if err:
                self.owner._write_action_log("stop_server", "stderr", err)
            self.owner._status(
                "Server stop requested."
                if code == 0
                else f"Stop returned {code}. {err or out}"
            )
            if code == 0 and after_success:
                QtCore.QTimer.singleShot(1200, after_success)

        def failed(message: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            self.owner._status(f"Stop failed: {message}")

        worker.signals.finished.connect(finished)
        worker.signals.failed.connect(failed)
        self.owner._status("Server stop requested; waiting for shutdown script.")
        self._pool.start(worker)

    def restart_server(self) -> None:
        self.stop_server(after_success=self.start_server)

    def start_lm(self) -> None:
        paths = self._resolved_paths()
        mon_py = paths["monitor_log"]
        if not mon_py.exists():
            self.owner._status("monitor_log.py not found.")
            return
        rp = self._rt_paths(self.owner.config_path)
        self._rm(rp["stop_log"])
        self._rm(rp["pid_log"])
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.owner.config_path

        lm_stdout = mgmt_logs.allocate_log_file(
            "monitor_log",
            label="monitor_log",
            metadata={"action": "start_monitor_log"},
        )
        try:
            self._spawn_logged(
                f'{self._pyexe()} "{mon_py}" --follow', lm_stdout, mon_py.parent, env=env
            )
            self.owner._status("Log monitor starting.")
        except Exception as e:
            self.owner._status(f"Log monitor start failed: {e}")

        if self._runtime_paths(self.owner.config_path)["log_monitor_enabled"]:
            self.owner.chk_live.setChecked(True)

    def stop_lm(self) -> None:
        rp = self._rt_paths(self.owner.config_path)
        self._mkflag(rp["stop_log"])
        self._stop_monitor_async(
            monitor_name="Log Monitor",
            pid_file=rp["pid_log"],
            fallback_command=(
                f"{self._pyexe()} -c \"import sys;sys.path.insert(0, r'{self._ctrl_dir}');"
                "from Tools import monitors;monitors.stop_log_monitor();print('OK')\""
            ),
            initial_timeout=20,
        )

    def start_cm(self) -> None:
        paths = self._resolved_paths()
        cm_py = paths["crash_monitor"]
        if not cm_py.exists():
            self.owner._status("crash_monitor.py not found.")
            return
        rp = self._rt_paths(self.owner.config_path)
        self._rm(rp["stop_crash"])
        self._rm(rp["pid_crash"])
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.owner.config_path

        cm_stdout = mgmt_logs.allocate_log_file(
            "crash_monitor",
            label="crash_monitor",
            metadata={"action": "start_crash_monitor"},
        )
        try:
            self._spawn_logged(f'{self._pyexe()} "{cm_py}"', cm_stdout, cm_py.parent, env=env)
            self.owner._status("Crash monitor starting.")
        except Exception as e:
            self.owner._status(f"Crash monitor start failed: {e}")

    def stop_cm(self) -> None:
        rp = self._rt_paths(self.owner.config_path)
        self._mkflag(rp["stop_crash"])
        self._stop_monitor_async(
            monitor_name="Crash Monitor",
            pid_file=rp["pid_crash"],
            fallback_command=(
                f"{self._pyexe()} -c \"import sys;sys.path.insert(0, r'{self._ctrl_dir}');"
                "from Tools import monitors;monitors.stop_crash_monitor();print('OK')\""
            ),
            initial_timeout=30,
        )

    def _stop_monitor_async(
        self,
        *,
        monitor_name: str,
        pid_file: Path,
        fallback_command: str,
        initial_timeout: int,
    ) -> None:
        worker = StopMonitorWorker(
            monitor_name=monitor_name,
            pid_file=pid_file,
            wait_for_monitor_exit=self._wait_for_monitor_exit,
            fallback_command=fallback_command,
            fallback_cwd=self._ctrl_dir,
            run_once=self._run_once,
            initial_timeout=initial_timeout,
        )
        self._workers.append(worker)

        def status(message: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            self.owner._status(message)

        worker.signals.status.connect(status)
        self.owner._status(f"Stopping {monitor_name}; waiting for monitor exit.")
        self._pool.start(worker)
