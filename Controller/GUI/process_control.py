"""
Process control helpers for Vein Manager GUI.

This controller centralizes start/stop logic for the server and monitors so the
Main window can delegate without carrying the implementation details.
"""

from __future__ import annotations

import os
import subprocess
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
        packaged: bool = False,
        tools_executable: Path | None = None,
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
        self._packaged = packaged
        self._tools_executable = tools_executable
        self._pool = QtCore.QThreadPool.globalInstance()
        self._workers: list[QtCore.QRunnable] = []

    # ------------------------ Server / monitors -------------------------------
    def _helper_command(self, action: str, script: Path, *script_args: str) -> str:
        if self._packaged:
            tool = self._tools_executable
            if tool is None or not tool.is_file():
                expected = tool or (self._ctrl_dir.parent / "VeinTools.exe")
                raise FileNotFoundError(
                    f"Packaged helper is missing: {expected}. Reinstall Vein Server Management."
                )
            return subprocess.list2cmdline(
                [str(tool), action, "--config", self.owner.config_path]
            )
        suffix = " ".join(script_args)
        return f'{self._pyexe()} "{script}"{f" {suffix}" if suffix else ""}'

    def _report_error(self, title: str, message: str, log_path: Path | None = None) -> None:
        self.owner._status(message)
        notify = getattr(self.owner, "_notify_action_error", None)
        if callable(notify):
            notify(title, message, log_path)

    @staticmethod
    def _write_launch_log(path: Path, command: str, out: str = "", err: str = "") -> None:
        try:
            sections = [f"Command: {command}"]
            if out:
                sections.extend(("", "STDOUT:", out.rstrip()))
            if err:
                sections.extend(("", "STDERR:", err.rstrip()))
            path.write_text("\n".join(sections) + "\n", encoding="utf-8", errors="replace")
        except Exception:
            pass

    @staticmethod
    def _set_busy(button, busy: bool) -> None:
        if button is not None:
            button.setEnabled(not busy)

    def start_server(self) -> None:
        if getattr(self.owner, "_server_available", True) is False:
            self._report_error(
                "No Server Available",
                "No Vein server is installed or selected. Open Quick Start to install or configure one.",
            )
            return
        paths = self._resolved_paths()
        py = paths["start_server"]
        if not self._packaged and not py.exists():
            self._report_error("Server Start Failed", f"Startup helper was not found: {py}")
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
            command = self._helper_command("start-server", py)
        except Exception as exc:
            self._report_error("Server Start Failed", str(exc), srv_stdout)
            return

        worker = RunOnceWorker(
            lambda cmd, **kwargs: self._run_once(cmd, env=env, **kwargs),
            command,
            cwd=self._ctrl_dir.parent if self._packaged else py.parent,
            timeout=600,
        )
        self._workers.append(worker)
        start_button = getattr(self.owner, "b_start", None)
        self._set_busy(start_button, True)

        def finished(code: int, out: str, err: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            self._set_busy(start_button, False)
            self._write_launch_log(srv_stdout, command, out, err)
            if out:
                self.owner._write_action_log("start_server", "stdout", out)
            if err:
                self.owner._write_action_log("start_server", "stderr", err)
            if code == 0:
                if "already running" in out.lower():
                    self.owner._status("Server is already running; no second process was started.")
                else:
                    self.owner._status("Server process launched; waiting for running status.")
                return
            detail = (err or out or "The startup helper returned no diagnostic output.").strip()
            if len(detail) > 2000:
                detail = "…" + detail[-2000:]
            self._report_error(
                "Server Start Failed",
                f"Startup returned exit code {code}. {detail}",
                srv_stdout,
            )

        def failed(message: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            self._set_busy(start_button, False)
            self._write_launch_log(srv_stdout, command, err=message)
            self._report_error(
                "Server Start Failed",
                f"Could not run the startup helper: {message}",
                srv_stdout,
            )

        worker.signals.finished.connect(finished)
        worker.signals.failed.connect(failed)
        self.owner._status(f"Starting server… Output: {srv_stdout}")
        self._pool.start(worker)

    def stop_server(self, *, after_success: Optional[Callable[[], None]] = None) -> None:
        paths = self._resolved_paths()
        py = paths["shutdown_server"]
        if not self._packaged and not py.exists():
            self._report_error("Server Stop Failed", f"Shutdown helper was not found: {py}")
            return
        try:
            command = self._helper_command("stop-server", py)
        except Exception as exc:
            self._report_error("Server Stop Failed", str(exc))
            return
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.owner.config_path
        stop_log = mgmt_logs.allocate_log_file(
            "vein_manager",
            label="stop_server",
            record_latest=False,
            metadata={"action": "stop_server", "config": self.owner.config_path},
        )
        worker = RunOnceWorker(
            lambda cmd, **kwargs: self._run_once(cmd, env=env, **kwargs),
            command,
            cwd=self._ctrl_dir.parent if self._packaged else py.parent,
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
            self._write_launch_log(stop_log, command, out, err)
            if code == 0:
                self.owner._status("Server stop completed.")
            else:
                detail = (err or out or "The shutdown helper returned no diagnostic output.").strip()
                self._report_error(
                    "Server Stop Failed",
                    f"Shutdown returned exit code {code}. {detail}",
                    stop_log,
                )
            if code == 0 and after_success:
                QtCore.QTimer.singleShot(1200, after_success)

        def failed(message: str) -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            self._write_launch_log(stop_log, command, err=message)
            self._report_error(
                "Server Stop Failed",
                f"Could not run the shutdown helper: {message}",
                stop_log,
            )

        worker.signals.finished.connect(finished)
        worker.signals.failed.connect(failed)
        self.owner._status("Server stop requested; waiting for shutdown script.")
        self._pool.start(worker)

    def restart_server(self) -> None:
        self.stop_server(after_success=self.start_server)

    def start_lm(self) -> None:
        if getattr(self.owner, "_server_available", True) is False:
            self._report_error(
                "No Server Available",
                "Install or select a Vein server in Quick Start before starting its log monitor.",
            )
            return
        paths = self._resolved_paths()
        mon_py = paths["monitor_log"]
        if not self._packaged and not mon_py.exists():
            self._report_error("Log Monitor Start Failed", f"Monitor helper was not found: {mon_py}")
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
            command = self._helper_command("monitor-log", mon_py, "--follow")
            self._spawn_logged(
                command,
                lm_stdout,
                self._ctrl_dir.parent if self._packaged else mon_py.parent,
                env=env,
            )
            self.owner._status("Log monitor starting.")
        except Exception as e:
            self._report_error("Log Monitor Start Failed", str(e), lm_stdout)

        if self._runtime_paths(self.owner.config_path)["log_monitor_enabled"]:
            self.owner.chk_live.setChecked(True)

    def stop_lm(self) -> None:
        rp = self._rt_paths(self.owner.config_path)
        self._mkflag(rp["stop_log"])
        monitor_py = self._resolved_paths().get("monitor_log", self._ctrl_dir / "monitor_log.py")
        try:
            fallback = (
                self._helper_command("stop-log-monitor", monitor_py)
                if self._packaged
                else (
                    f"{self._pyexe()} -c \"import sys;sys.path.insert(0, r'{self._ctrl_dir}');"
                    "from Tools import monitors;monitors.stop_log_monitor();print('OK')\""
                )
            )
        except Exception as exc:
            self._report_error("Log Monitor Stop Failed", str(exc))
            return
        self._stop_monitor_async(
            monitor_name="Log Monitor",
            pid_file=rp["pid_log"],
            fallback_command=fallback,
            initial_timeout=20,
        )

    def start_cm(self) -> None:
        if getattr(self.owner, "_server_available", True) is False:
            self._report_error(
                "No Server Available",
                "Install or select a Vein server in Quick Start before starting its crash monitor.",
            )
            return
        paths = self._resolved_paths()
        cm_py = paths["crash_monitor"]
        if not self._packaged and not cm_py.exists():
            self._report_error("Crash Monitor Start Failed", f"Monitor helper was not found: {cm_py}")
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
            command = self._helper_command("crash-monitor", cm_py)
            self._spawn_logged(
                command,
                cm_stdout,
                self._ctrl_dir.parent if self._packaged else cm_py.parent,
                env=env,
            )
            self.owner._status("Crash monitor starting.")
        except Exception as e:
            self._report_error("Crash Monitor Start Failed", str(e), cm_stdout)

    def stop_cm(self) -> None:
        rp = self._rt_paths(self.owner.config_path)
        self._mkflag(rp["stop_crash"])
        monitor_py = self._resolved_paths().get("crash_monitor", self._ctrl_dir / "crash_monitor.py")
        try:
            fallback = (
                self._helper_command("stop-crash-monitor", monitor_py)
                if self._packaged
                else (
                    f"{self._pyexe()} -c \"import sys;sys.path.insert(0, r'{self._ctrl_dir}');"
                    "from Tools import monitors;monitors.stop_crash_monitor();print('OK')\""
                )
            )
        except Exception as exc:
            self._report_error("Crash Monitor Stop Failed", str(exc))
            return
        self._stop_monitor_async(
            monitor_name="Crash Monitor",
            pid_file=rp["pid_crash"],
            fallback_command=fallback,
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
            if "still running" in message.lower():
                self._report_error(f"{monitor_name} Stop Failed", message)
            else:
                self.owner._status(message)

        worker.signals.status.connect(status)
        self.owner._status(f"Stopping {monitor_name}; waiting for monitor exit.")
        self._pool.start(worker)
