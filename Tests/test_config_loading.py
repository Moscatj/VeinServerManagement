from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

import config as config_module  # noqa: E402


class ConfigLoadingTests(unittest.TestCase):
    def test_migrate_v2_layout_populates_legacy_keys(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            mgmt_root = Path(tmp)
            cfg = {
                "version": 2,
                "paths": {
                    "server_root": "GameServer",
                    "saves_dir": "GameServer/Saved",
                    "logs_dir": "GameServer/Logs",
                    "mgmt_log_dir": "Logs",
                    "runtime_dir": "Runtime",
                    "backup_root": "Backups",
                },
                "server": {
                    "executables": ["VeinServer.exe"],
                    "preferred_exe": "VeinServer.exe",
                    "ports": {"game": "7777", "query": "27015"},
                    "max_players": "16",
                },
                "monitor": {"enabled": True, "heartbeat_seconds": "30"},
                "crash_monitor": {"enabled": False, "heartbeat_seconds": "10"},
                "backups": {"enabled": True, "root": "Backups"},
                "steam": {"app_id": "123", "steamcmd_path": "SteamCMD/steamcmd.exe"},
            }

            migrated = config_module._migrate_v2_layout(cfg, mgmt_root)

        self.assertEqual(migrated["server_dir"], "GameServer")
        self.assertEqual(migrated["save_dir"], "GameServer/Saved")
        self.assertEqual(migrated["logs_dir"], "GameServer/Logs")
        self.assertEqual(migrated["mgmt_log_dir"], "Logs")
        self.assertEqual(migrated["server_executables"], ["VeinServer.exe"])
        self.assertEqual(migrated["preferred_exe"], "VeinServer.exe")
        self.assertEqual(migrated["game_port"], 7777)
        self.assertEqual(migrated["query_port"], 27015)
        self.assertEqual(migrated["max_players"], 16)
        self.assertEqual(migrated["monitor_heartbeat_interval_seconds"], 30)
        self.assertEqual(migrated["crash_monitor_interval_seconds"], 10)
        self.assertTrue(migrated["features"]["enable_log_monitor"])
        self.assertFalse(migrated["features"]["enable_crash_monitor"])
        self.assertTrue(migrated["features"]["enable_backups"])
        self.assertEqual(migrated["app_id"], "123")

    def test_normalize_paths_makes_known_relative_paths_absolute(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            mgmt_root = Path(tmp)
            cfg = {
                "server_dir": "GameServer",
                "backup_root": "Backups",
                "runtime_dir": "Runtime",
                "mgmt_log_dir": "Logs",
                "paths": {
                    "logs_dir": "GameServer/Saved/Logs",
                    "saves_dir": "GameServer/Saved",
                },
                "backups": {"root": "Backups/Nightly"},
            }

            normalized = config_module._normalize_paths(cfg, mgmt_root)

            self.assertEqual(normalized["server_dir"], str((mgmt_root / "GameServer").resolve()))
            self.assertEqual(normalized["backup_root"], str((mgmt_root / "Backups").resolve()))
            self.assertEqual(normalized["runtime_dir"], str((mgmt_root / "Runtime").resolve()))
            self.assertEqual(normalized["mgmt_log_dir"], str((mgmt_root / "Logs").resolve()))
            self.assertEqual(
                normalized["paths"]["logs_dir"],
                str((mgmt_root / "GameServer" / "Saved" / "Logs").resolve()),
            )
            self.assertEqual(
                normalized["backups"]["root"],
                str((mgmt_root / "Backups" / "Nightly").resolve()),
            )


if __name__ == "__main__":
    unittest.main()
