from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

import config as config_module  # noqa: E402


class ConfigLoadFullTests(unittest.TestCase):
    def tearDown(self) -> None:
        config_module._CONFIG_CACHE = None

    def test_load_first_existing_prefers_env_yaml(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            yaml_cfg = base / "selected.yaml"
            json_cfg = base / "fallback.json"
            yaml_cfg.write_text("server_dir: Game\n", encoding="utf-8")
            json_cfg.write_text(json.dumps({"server_dir": "JsonGame"}), encoding="utf-8")

            with mock.patch.dict(os.environ, {"VEIN_CONFIG": str(yaml_cfg)}, clear=False):
                path, data = config_module._load_first_existing([json_cfg])

        self.assertEqual(path, yaml_cfg)
        self.assertEqual(data["server_dir"], "Game")

    def test_load_config_from_temp_yaml_normalizes_and_caches(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            mgmt = Path(tmp)
            server = mgmt / "Server"
            server.mkdir()
            cfg = mgmt / "config.yaml"
            cfg.write_text(
                """
version: 2
paths:
  server_root: Server
  runtime_dir: Runtime
  mgmt_log_dir: Logs
  backup_root: Backups
server:
  executables:
    - VeinServer.exe
  ports:
    game: 7777
    query: 27015
backups:
  enabled: true
  root: Backups
""",
                encoding="utf-8",
            )

            config_module._CONFIG_CACHE = None
            with mock.patch.dict(os.environ, {"VEIN_CONFIG": str(cfg)}, clear=False), mock.patch.object(
                config_module,
                "_mgmt_root",
                return_value=mgmt,
            ):
                loaded = config_module.load_config()
                cached = config_module.load_config()

        self.assertIs(loaded, cached)
        self.assertEqual(loaded["server_dir"], str(server.resolve()))
        self.assertEqual(loaded["runtime_dir"], str((mgmt / "Runtime").resolve()))
        self.assertEqual(loaded["backup_root"], str((mgmt / "Backups").resolve()))
        self.assertEqual(loaded["game_port"], 7777)

    def test_load_config_raises_for_missing_server_dir(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = Path(tmp) / "bad.yaml"
            cfg.write_text("version: 2\n", encoding="utf-8")
            config_module._CONFIG_CACHE = None
            with mock.patch.dict(os.environ, {"VEIN_CONFIG": str(cfg)}, clear=False), mock.patch.object(
                config_module,
                "_mgmt_root",
                return_value=Path(tmp),
            ):
                with self.assertRaisesRegex(ValueError, "server_dir"):
                    config_module.load_config()


if __name__ == "__main__":
    unittest.main()
