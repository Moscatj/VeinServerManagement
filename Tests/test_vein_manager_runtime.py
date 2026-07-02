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


class VeinManagerRuntimeConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        vein_manager._RUNTIME_CFG_CACHE.clear()

    def tearDown(self) -> None:
        vein_manager._RUNTIME_CFG_CACHE.clear()

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
