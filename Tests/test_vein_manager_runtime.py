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

import vein_manager  # noqa: E402
from Tools.setup_state import SetupAssessment, SetupState, SetupWorkflow  # noqa: E402


class VeinManagerRuntimeConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        vein_manager._RUNTIME_CFG_CACHE.clear()

    def tearDown(self) -> None:
        vein_manager._RUNTIME_CFG_CACHE.clear()

    def test_primary_server_action_routes_setup_start_and_stop(self) -> None:
        owner = mock.Mock()

        for action in ("setup", "start", "stop"):
            owner.reset_mock()
            owner.b_server_action.property.return_value = action
            vein_manager.Main._activate_primary_server_action(owner)

            if action == "setup":
                owner._on_view_selected.assert_called_once_with("monitor.quick_start")
            elif action == "start":
                owner.start_server.assert_called_once_with()
            else:
                owner.stop_server.assert_called_once_with()

    def test_completed_quick_start_opens_server_settings(self) -> None:
        owner = mock.Mock()
        owner.edQuickServerRoot.text.return_value = "C:/VeinServer"
        owner.config_path = "Config/config.yaml"
        owner._quick_start_existing_executables = None
        assessment = SetupAssessment(
            SetupState.CONFIGURED,
            SetupWorkflow.EXISTING_SERVER,
            "Edit Server Settings",
            "Setup completed.",
        )

        with mock.patch.object(
            vein_manager.QtWidgets.QMessageBox,
            "question",
            return_value=vein_manager.QtWidgets.QMessageBox.Yes,
        ), mock.patch.object(
            vein_manager, "apply_quick_start", return_value="Applied"
        ), mock.patch.object(
            vein_manager, "assess_server_setup", return_value=(mock.Mock(), assessment, mock.Mock())
        ), mock.patch.object(
            vein_manager.QtCore.QTimer, "singleShot"
        ):
            vein_manager.Main._confirm_apply_quick_start(owner)

        owner._on_view_selected.assert_called_once_with("monitor.server_config")
        self.assertIn("Opening Server Settings", owner.lblQuickStartStatus.setText.call_args.args[0])

    def test_incomplete_quick_start_stays_in_wizard(self) -> None:
        owner = mock.Mock()
        owner.edQuickServerRoot.text.return_value = "C:/VeinServer"
        owner.config_path = "Config/config.yaml"
        owner._quick_start_existing_executables = None
        assessment = SetupAssessment(
            SetupState.NEW_OR_MISSING,
            SetupWorkflow.NEW_SERVER,
            "Install Server",
            "Binaries are missing.",
        )

        with mock.patch.object(
            vein_manager.QtWidgets.QMessageBox,
            "question",
            return_value=vein_manager.QtWidgets.QMessageBox.Yes,
        ), mock.patch.object(
            vein_manager, "apply_quick_start", return_value="Applied"
        ), mock.patch.object(
            vein_manager, "assess_server_setup", return_value=(mock.Mock(), assessment, mock.Mock())
        ), mock.patch.object(
            vein_manager.QtCore.QTimer, "singleShot"
        ):
            vein_manager.Main._confirm_apply_quick_start(owner)

        owner._on_view_selected.assert_not_called()

    def test_server_settings_refresh_preserves_unsaved_changes_when_declined(self) -> None:
        owner = mock.Mock()
        owner._server_identity_dirty = True
        owner._server_settings_apply_notice = "Previous result"
        with mock.patch.object(
            vein_manager.QtWidgets.QMessageBox,
            "question",
            return_value=vein_manager.QtWidgets.QMessageBox.No,
        ):
            vein_manager.Main._request_server_config_preview_refresh(owner)

        self.assertTrue(owner._server_identity_dirty)
        self.assertEqual(owner._server_settings_apply_notice, "Previous result")
        owner._refresh_server_config_preview.assert_not_called()

    def test_server_settings_refresh_discards_only_after_confirmation(self) -> None:
        owner = mock.Mock()
        owner._server_identity_dirty = True
        owner._server_settings_apply_notice = "Previous result"
        with mock.patch.object(
            vein_manager.QtWidgets.QMessageBox,
            "question",
            return_value=vein_manager.QtWidgets.QMessageBox.Yes,
        ):
            vein_manager.Main._request_server_config_preview_refresh(owner)

        self.assertFalse(owner._server_identity_dirty)
        self.assertEqual(owner._server_settings_apply_notice, "")
        owner._refresh_server_config_preview.assert_called_once_with()

    def test_server_settings_apply_preserves_validation_outcome_through_refresh(self) -> None:
        owner = mock.Mock()
        payload = {
            "ok": True,
            "action": "apply",
            "summary": "Proposed Server Settings changes:\n- Server name",
            "diffs": {"Game.ini": "+ServerName=Updated\n"},
            "changed_files": ["Game.ini"],
            "backups": ["Game.ini.backup"],
            "validation": [
                {"status": "PASS", "name": "server.config.server_name"},
                {"status": "WARN", "name": "server.config.admins"},
            ],
        }

        vein_manager.Main._apply_identity_access_edit_result(owner, payload)

        self.assertIn("PASS=1, WARN=1", owner._server_settings_apply_notice)
        self.assertIn("next server start or restart", owner._server_settings_apply_notice)
        self.assertEqual(owner._server_settings_apply_notice_kind, "warning")
        owner._refresh_server_config_preview.assert_called_once_with()

    def test_source_python_uses_console_sibling_of_pythonw(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            pythonw = runtime / "pythonw.exe"
            python = runtime / "python.exe"
            pythonw.write_text("fixture", encoding="utf-8")
            python.write_text("fixture", encoding="utf-8")

            selected = vein_manager._source_python_executable(
                pythonw,
                windows=True,
            )

        self.assertEqual(selected, python)

    def test_source_python_keeps_pythonw_when_console_sibling_is_missing(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            pythonw = Path(tmp) / "pythonw.exe"
            pythonw.write_text("fixture", encoding="utf-8")

            selected = vein_manager._source_python_executable(
                pythonw,
                windows=True,
            )

        self.assertEqual(selected, pythonw)

    def test_pyexe_prefers_override_then_current_runtime(self) -> None:
        current = ROOT / "Python Runtime" / "python.exe"
        with mock.patch.object(vein_manager, "PYEXE_ENV", "py -3.12"):
            self.assertEqual(vein_manager._pyexe(), "py -3.12")

        with mock.patch.object(vein_manager, "PYEXE_ENV", ""), mock.patch.object(
            vein_manager.sys,
            "executable",
            str(current),
        ):
            selected = vein_manager._pyexe()

        self.assertEqual(selected, f'"{current}"')

    def test_runtime_loader_does_not_use_comment_preserving_yaml_loader(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text("version: 2\n", encoding="utf-8")
            resolved = {
                "runtime_dir": str(Path(tmp) / "Runtime"),
                "server_dir": str(Path(tmp)),
                "backup_root": str(Path(tmp) / "Backups"),
                "features": {},
            }

            with mock.patch.object(
                vein_manager,
                "_load_any_config",
                side_effect=AssertionError("ruamel path should not be used"),
            ), mock.patch.object(
                vein_manager,
                "_load_cfg_with_config_module",
                return_value=resolved,
            ) as load_resolved:
                first = vein_manager._load_cfg_for_runtime(str(cfg_path))
                second = vein_manager._load_cfg_for_runtime(str(cfg_path))

        self.assertEqual(first["runtime_dir"], resolved["runtime_dir"])
        self.assertEqual(second["runtime_dir"], resolved["runtime_dir"])
        load_resolved.assert_called_once_with(str(cfg_path))

    def test_runtime_paths_use_log_monitor_state_file(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = {
                "runtime_dir": str(base / "Runtime"),
                "server_dir": str(base / "Server"),
                "logs_dir": str(base / "GameLogs"),
                "backup_root": str(base / "Backups"),
                "features": {"enable_log_monitor": True},
                "log_monitor": {"state_file": str(base / "Runtime" / "custom-log-state.json")},
            }
            with mock.patch.object(vein_manager, "_load_cfg_for_runtime", return_value=cfg):
                rt = vein_manager._rt_paths(str(base / "config.yaml"))
                paths = vein_manager._runtime_paths(str(base / "config.yaml"))

        self.assertEqual(rt["state_log"], base / "Runtime" / "custom-log-state.json")
        self.assertEqual(paths["state_log"], base / "Runtime" / "custom-log-state.json")

    def test_runtime_loader_falls_back_to_pyyaml_without_ruamel(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        "paths:",
                        "  runtime_dir: Runtime",
                        "  server_root: ..",
                        "  logs_dir: GameLogs",
                        "  absolute_log_file: GameLogs/Vein.log",
                        "features:",
                        "  enable_log_monitor: true",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                vein_manager,
                "_load_cfg_with_config_module",
                side_effect=ValueError("invalid while editing"),
            ), mock.patch.object(
                vein_manager,
                "_load_any_config",
                side_effect=AssertionError("ruamel path should not be used"),
            ):
                cfg = vein_manager._load_cfg_for_runtime(str(cfg_path))
                paths = vein_manager._runtime_paths(str(cfg_path))

        self.assertEqual(cfg["paths"]["runtime_dir"], "Runtime")
        self.assertTrue(cfg["features"]["enable_log_monitor"])
        self.assertEqual(paths["runtime_dir"], Path("Runtime"))
        self.assertEqual(paths["logs_dir"], Path("GameLogs"))
        self.assertEqual(paths["absolute_log_file"], Path("GameLogs/Vein.log"))

    @unittest.skipUnless(vein_manager._HAVE_RUAMEL, "ruamel.yaml not installed")
    def test_yaml_config_editor_loads_round_trip_document(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                "# keep this comment\nserver:\n  max_players: 8\n",
                encoding="utf-8",
            )

            data, kind, ydoc = vein_manager._load_any_config(cfg_path)
            ydoc["server"]["max_players"] = 10
            rendered = vein_manager._dump_any_config(data, kind, ydoc=ydoc)

        self.assertEqual(kind, "yaml")
        self.assertIsNotNone(ydoc)
        self.assertIn("# keep this comment", rendered)
        self.assertIn("max_players: 10", rendered)
        self.assertFalse(rendered.lstrip().startswith("{"))

    @unittest.skipUnless(vein_manager._HAVE_RUAMEL, "ruamel.yaml not installed")
    def test_yaml_dump_without_round_trip_doc_stays_yaml(self) -> None:
        rendered = vein_manager._dump_any_config(
            {"server": {"max_players": 10}},
            "yaml",
            ydoc=None,
        )

        self.assertIn("server:", rendered)
        self.assertIn("max_players: 10", rendered)
        self.assertFalse(rendered.lstrip().startswith("{"))


if __name__ == "__main__":
    unittest.main()
