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

from Tools import config_summary, paths  # noqa: E402


class PathsAndSummaryTests(unittest.TestCase):
    def test_paths_use_config_and_fallbacks(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            save_dir = base / "Saved"
            save_dir.mkdir()
            found = save_dir / "B.sav"
            found.write_text("save", encoding="utf-8")
            cfg = {
                "server_dir": str(base / "Server"),
                "save_dir": str(save_dir),
                "save_filenames": ["A.sav", "B.sav"],
                "absolute_log_file": str(base / "Logs" / "Vein.log"),
            }

            with mock.patch.dict(paths.config, cfg, clear=True), mock.patch.object(
                paths,
                "get_path",
                side_effect=lambda key: cfg.get(key, ""),
            ):
                self.assertEqual(paths.server_dir(), base / "Server")
                self.assertEqual(paths.save_dir(), save_dir)
                self.assertEqual(paths.resolve_save_file(), found)
                self.assertEqual(paths.absolute_log_file(), str(base / "Logs" / "Vein.log"))

    def test_resolve_save_file_returns_first_candidate_when_none_exist(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = {"server_dir": str(base / "Server"), "save_filenames": ["Server.vns"]}
            with mock.patch.dict(paths.config, cfg, clear=True), mock.patch.object(
                paths,
                "get_path",
                side_effect=lambda key: cfg.get(key, ""),
            ):
                self.assertEqual(
                    paths.resolve_save_file(),
                    base / "Server" / "Vein" / "Saved" / "SaveGames" / "Server.vns",
                )

    def test_summarize_config_projects_core_fields(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            exe = base / "Server" / "VeinServer.exe"
            cfg = {
                "server_executables": ["VeinServer.exe"],
                "map_path": "/Game/Test",
                "max_players": 12,
                "game_port": 7777,
                "query_port": 27015,
                "multi_home_ip": "127.0.0.1",
                "steamcmd_path": "steamcmd.exe",
                "monitor_log_wait_timeout_seconds": 20,
                "headless_mode": True,
                "app_id": "123",
                "features": {"enable_discord": False},
                "enable_query_port": False,
            }
            with mock.patch.object(config_summary.paths, "server_dir", return_value=base / "Server"), mock.patch.object(
                config_summary.paths,
                "logs_dir",
                return_value=base / "Logs",
            ), mock.patch.object(
                config_summary.paths,
                "save_dir",
                return_value=base / "Saved",
            ), mock.patch.object(
                config_summary,
                "resolve_server_executable",
                return_value=exe,
            ), mock.patch.object(
                config_summary,
                "backups_cfg",
                return_value={"root": str(base / "Backups"), "folders": {}, "retention": {}, "enable": True},
            ), mock.patch.dict(config_summary.config, cfg, clear=True):
                summary = config_summary.summarize_config()

        self.assertEqual(summary["server_dir"], str(base / "Server"))
        self.assertEqual(summary["executable_selected"], str(exe))
        self.assertEqual(summary["map_url"], "/Game/Test")
        self.assertEqual(summary["max_players"], 12)
        self.assertFalse(summary["features"]["enable_discord"])
        self.assertFalse(summary["features"]["enable_query_port"])


if __name__ == "__main__":
    unittest.main()
