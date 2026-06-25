from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import config_io  # noqa: E402


class ConfigIoTests(unittest.TestCase):
    def test_discover_cfg_path_prefers_explicit_existing_path(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text("version: 2\n", encoding="utf-8")

            discovered = config_io._discover_cfg_path(cfg)

        self.assertEqual(discovered, cfg)

    def test_load_and_validate_config_projects_typed_view(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            raw = {
                "server_dir": str(base / "Server"),
                "runtime_dir": str(base / "Runtime"),
                "logs_dir": str(base / "Logs"),
                "save_dir": str(base / "Saved"),
                "absolute_log_file": str(base / "Logs" / "Vein.log"),
                "server_executables": ["A.exe", "B.exe"],
                "preferred_exe": "B.exe",
                "monitor": {
                    "heartbeat_seconds": "15",
                    "fresh_window_multiplier": "3.5",
                    "discord": {"enabled": True},
                },
                "steam": {"app_id": "123"},
                "backups": {"root": str(base / "Backups")},
            }

            with mock.patch.object(config_io, "load_config", return_value=raw), mock.patch.object(
                config_io,
                "_discover_cfg_path",
                return_value=base / "config.yaml",
            ):
                view = config_io.load_and_validate_config()

        self.assertEqual(view.selected_exe, base / "Server" / "B.exe")
        self.assertEqual(view.hb_seconds, 15)
        self.assertEqual(view.fresh_window_multiplier, 3.5)
        self.assertEqual(view.steam["app_id"], "123")
        self.assertTrue(view.discord["enabled"])

    def test_load_and_validate_config_wraps_errors_when_not_fatal(self) -> None:
        with mock.patch.object(config_io, "load_config", side_effect=ValueError("bad")):
            with self.assertRaisesRegex(RuntimeError, "Could not load config"):
                config_io.load_and_validate_config(fatal=False)


if __name__ == "__main__":
    unittest.main()
