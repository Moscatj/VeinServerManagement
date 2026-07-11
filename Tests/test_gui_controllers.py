from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from PySide6 import QtWidgets  # noqa: E402

from GUI.config_controller import ConfigController  # noqa: E402
from GUI.nav_control import NavigationController  # noqa: E402
from GUI.process_control import ProcessController  # noqa: E402


def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class GuiControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = app()

    def test_navigation_controller_registers_selects_and_pins_views(self) -> None:
        owner = mock.Mock()
        owner.content_stack = QtWidgets.QStackedWidget()
        owner.side_tabs = QtWidgets.QTabWidget()
        owner._view_routes = {}
        owner._view_factories = {}
        owner._side_tab_store = {}
        owner._set_right_panel_visible = mock.Mock()
        controller = NavigationController(owner)
        widget = QtWidgets.QLabel("Main")
        callback = mock.Mock()

        controller.register_view("main", widget, callback)
        controller.on_view_selected("main")
        controller.ensure_tab_present("Tools", lambda: QtWidgets.QLabel("Tools"))
        controller.ensure_tab_present("Tools", None)

        self.assertEqual(owner.content_stack.currentWidget(), widget)
        callback.assert_called_once()
        self.assertEqual(owner.side_tabs.count(), 1)
        owner._set_right_panel_visible.assert_called_once_with(True)

    def test_config_controller_selects_config_and_delegates_filter(self) -> None:
        owner = mock.Mock()
        owner.config_dir = "Config"
        owner.ed_cfgdir = QtWidgets.QLineEdit("Config")
        owner.filter = QtWidgets.QLineEdit("abc")
        owner.load_config_text = mock.Mock()
        owner.watch_config = mock.Mock()
        controller = ConfigController(owner)
        controller.renderer = mock.Mock()

        controller.apply_filter("server")
        controller.build_tabs({"a": 1})
        controller.clear_filter()
        controller.cfg_selected("config.yaml")

        controller.renderer.apply_filter.assert_called_once_with("server")
        controller.renderer.build_tabs.assert_called_once_with({"a": 1})
        self.assertEqual(owner.filter.text(), "")
        self.assertEqual(owner.config_path, str(Path("Config") / "config.yaml"))
        owner.load_config_text.assert_called_once()
        owner.watch_config.assert_called_once()

    def test_process_controller_start_and_stop_server_delegate_safely(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            start = base / "start_server.py"
            stop = base / "shutdown_server.py"
            start.write_text("", encoding="utf-8")
            stop.write_text("", encoding="utf-8")
            owner = mock.Mock()
            owner.config_path = str(base / "config.yaml")
            owner._status = mock.Mock()
            owner._notify_action_error = mock.Mock()
            owner._write_action_log = mock.Mock()
            spawn = mock.Mock()
            run_once = mock.Mock(return_value=(0, "out", "err"))
            controller = ProcessController(
                owner,
                pyexe=lambda: "python",
                resolved_paths=lambda: {"start_server": start, "shutdown_server": stop},
                rt_paths=lambda _: {},
                runtime_paths=lambda _: {"log_monitor_enabled": False},
                spawn_logged=spawn,
                run_once=run_once,
                mkflag=mock.Mock(),
                rm=mock.Mock(),
                wait_for_monitor_exit=mock.Mock(return_value=True),
                ctrl_dir=base,
            )
            with mock.patch("GUI.process_control.mgmt_logs.allocate_log_file", return_value=base / "run.log"), mock.patch.object(
                controller._pool, "start", side_effect=lambda worker: worker.run()
            ):
                controller.start_server()
                controller.stop_server()

        spawn.assert_not_called()
        self.assertEqual(run_once.call_count, 2)
        self.assertIn('python "', run_once.call_args_list[0].args[0])
        self.assertIn("start_server.py", run_once.call_args_list[0].args[0])
        owner._write_action_log.assert_any_call("start_server", "stdout", "out")
        owner._write_action_log.assert_any_call("start_server", "stderr", "err")
        owner._write_action_log.assert_any_call("stop_server", "stdout", "out")
        owner._write_action_log.assert_any_call("stop_server", "stderr", "err")
        owner._status.assert_any_call("Server process launched; waiting for running status.")
        owner._status.assert_any_call("Server stop requested; waiting for shutdown script.")
        owner._status.assert_any_call("Server stop requested.")

    def test_packaged_start_uses_vein_tools_and_surfaces_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            ctrl = base / "Controller"
            ctrl.mkdir()
            tools = base / "VeinTools.exe"
            tools.write_text("fixture", encoding="utf-8")
            config = base / "Config" / "config.yaml"
            config.parent.mkdir()
            config.write_text("version: '2.2'\n", encoding="utf-8")
            log_path = base / "Logs" / "start.log"
            log_path.parent.mkdir()
            owner = mock.Mock()
            owner.config_path = str(config)
            owner._status = mock.Mock()
            owner._notify_action_error = mock.Mock()
            owner._write_action_log = mock.Mock()
            owner.b_start = QtWidgets.QPushButton("Start Server")
            run_once = mock.Mock(return_value=(1, "", "No server executable found"))
            controller = ProcessController(
                owner,
                pyexe=lambda: "py -3",
                resolved_paths=lambda: {"start_server": ctrl / "start_server.py"},
                rt_paths=lambda _: {},
                runtime_paths=lambda _: {"log_monitor_enabled": False},
                spawn_logged=mock.Mock(),
                run_once=run_once,
                mkflag=mock.Mock(),
                rm=mock.Mock(),
                wait_for_monitor_exit=mock.Mock(return_value=True),
                ctrl_dir=ctrl,
                packaged=True,
                tools_executable=tools,
            )

            with mock.patch(
                "GUI.process_control.mgmt_logs.allocate_log_file", return_value=log_path
            ), mock.patch.object(
                controller._pool, "start", side_effect=lambda worker: worker.run()
            ):
                controller.start_server()

            command = run_once.call_args.args[0]
            self.assertIn(str(tools), command)
            self.assertIn("start-server", command)
            self.assertIn("--config", command)
            self.assertNotIn("py -3", command)
            owner._notify_action_error.assert_called_once()
            self.assertIn("exit code 1", owner._notify_action_error.call_args.args[1])
            self.assertIn("No server executable found", log_path.read_text(encoding="utf-8"))
            self.assertTrue(owner.b_start.isEnabled())

    def test_packaged_start_reports_missing_vein_tools(self) -> None:
        owner = mock.Mock()
        owner.config_path = "Config/config.yaml"
        owner._status = mock.Mock()
        owner._notify_action_error = mock.Mock()
        controller = ProcessController(
            owner,
            pyexe=lambda: "py -3",
            resolved_paths=lambda: {"start_server": Path("Controller/start_server.py")},
            rt_paths=lambda _: {},
            runtime_paths=lambda _: {"log_monitor_enabled": False},
            spawn_logged=mock.Mock(),
            run_once=mock.Mock(),
            mkflag=mock.Mock(),
            rm=mock.Mock(),
            wait_for_monitor_exit=mock.Mock(return_value=True),
            ctrl_dir=ROOT / "Controller",
            packaged=True,
            tools_executable=ROOT / "missing-VeinTools.exe",
        )

        with mock.patch(
            "GUI.process_control.mgmt_logs.allocate_log_file",
            return_value=ROOT / "Logs" / "missing.log",
        ):
            controller.start_server()

        owner._notify_action_error.assert_called_once()
        self.assertIn("Reinstall", owner._notify_action_error.call_args.args[1])

    def test_process_controller_stop_server_runs_off_gui_thread(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            stop = base / "shutdown_server.py"
            stop.write_text("", encoding="utf-8")
            owner = mock.Mock()
            owner.config_path = str(base / "config.yaml")
            owner._status = mock.Mock()
            owner._write_action_log = mock.Mock()
            run_once = mock.Mock(return_value=(0, "out", "err"))
            controller = ProcessController(
                owner,
                pyexe=lambda: "python",
                resolved_paths=lambda: {"shutdown_server": stop},
                rt_paths=lambda _: {},
                runtime_paths=lambda _: {"log_monitor_enabled": False},
                spawn_logged=mock.Mock(),
                run_once=run_once,
                mkflag=mock.Mock(),
                rm=mock.Mock(),
                wait_for_monitor_exit=mock.Mock(return_value=True),
                ctrl_dir=base,
            )
            with mock.patch.object(controller._pool, "start") as start:
                controller.stop_server()

        run_once.assert_not_called()
        start.assert_called_once()
        owner._status.assert_called_once_with("Server stop requested; waiting for shutdown script.")

    def test_process_controller_stop_log_monitor_runs_off_gui_thread(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            pid = base / "log_monitor.pid"
            stop_flag = base / "stop_log_monitor.flag"
            owner = mock.Mock()
            owner.config_path = str(base / "config.yaml")
            owner._status = mock.Mock()
            wait_for_exit = mock.Mock(return_value=True)
            controller = ProcessController(
                owner,
                pyexe=lambda: "python",
                resolved_paths=lambda: {},
                rt_paths=lambda _: {"pid_log": pid, "stop_log": stop_flag},
                runtime_paths=lambda _: {"log_monitor_enabled": False},
                spawn_logged=mock.Mock(),
                run_once=mock.Mock(),
                mkflag=mock.Mock(),
                rm=mock.Mock(),
                wait_for_monitor_exit=wait_for_exit,
                ctrl_dir=base,
            )
            with mock.patch.object(controller._pool, "start") as start:
                controller.stop_lm()

        wait_for_exit.assert_not_called()
        start.assert_called_once()
        controller._mkflag.assert_called_once_with(stop_flag)
        owner._status.assert_called_once_with("Stopping Log Monitor; waiting for monitor exit.")

    def test_process_controller_stop_monitors_report_completion_from_worker(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            pid_log = base / "log_monitor.pid"
            pid_crash = base / "crash_monitor.pid"
            owner = mock.Mock()
            owner.config_path = str(base / "config.yaml")
            owner._status = mock.Mock()
            wait_for_exit = mock.Mock(return_value=True)
            controller = ProcessController(
                owner,
                pyexe=lambda: "python",
                resolved_paths=lambda: {},
                rt_paths=lambda _: {
                    "pid_log": pid_log,
                    "stop_log": base / "stop_log_monitor.flag",
                    "pid_crash": pid_crash,
                    "stop_crash": base / "stop_crash_monitor.flag",
                },
                runtime_paths=lambda _: {"log_monitor_enabled": False},
                spawn_logged=mock.Mock(),
                run_once=mock.Mock(),
                mkflag=mock.Mock(),
                rm=mock.Mock(),
                wait_for_monitor_exit=wait_for_exit,
                ctrl_dir=base,
            )
            with mock.patch.object(controller._pool, "start", side_effect=lambda worker: worker.run()):
                controller.stop_lm()
                controller.stop_cm()

        wait_for_exit.assert_any_call(pid_log, timeout_sec=20)
        wait_for_exit.assert_any_call(pid_crash, timeout_sec=30)
        owner._status.assert_any_call("Log Monitor stopped.")
        owner._status.assert_any_call("Crash Monitor stopped.")


if __name__ == "__main__":
    unittest.main()
