from __future__ import annotations

import os
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

os.environ.setdefault("VEIN_CONFIG", str(ROOT / "Config" / "config.example.yaml"))

import start_server  # noqa: E402


class StartServerOrchestrationTests(unittest.TestCase):
    def _recovery_config(self, root: Path, *, enabled: bool = True) -> SimpleNamespace:
        config_path = root / "Config" / "config.yaml"
        config_path.parent.mkdir()
        config_path.write_text("version: '2.4'\n", encoding="utf-8")
        return SimpleNamespace(
            path=config_path,
            raw={
                "backup_root": str(root / "Backups"),
                "backups": {
                    "recovery": {"restore_missing_on_start": enabled},
                    "save_filenames": ["Server.vns"],
                },
            },
            save_dir=root / "SaveGames",
            runtime_dir=root / "Runtime",
            server_dir=root / "Server",
            server_executables=["VeinServer.exe"],
        )

    def _save_archive(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "reason": "Crash",
            "created_utc": "2026-07-23T12:00:00Z",
            "save_filename": "Server.vns",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr("Server.vns", payload)
            bundle.writestr("manifest.json", json.dumps(manifest))

    def test_missing_save_is_recovered_before_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vcfg = self._recovery_config(root)
            self._save_archive(root / "Backups" / "Crash" / "Server_Crash.zip", b"safe")

            with mock.patch.object(
                start_server, "find_running_server", return_value=None
            ), mock.patch.object(start_server, "send_discord_message"):
                allowed = start_server._startup_recovery_preflight(vcfg)

            self.assertTrue(allowed)
            self.assertEqual((vcfg.save_dir / "Server.vns").read_bytes(), b"safe")

    def test_invalid_prior_save_backup_blocks_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vcfg = self._recovery_config(root)
            archive = root / "Backups" / "Crash" / "Server_Crash.zip"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(b"damaged")

            with mock.patch.object(
                start_server, "find_running_server", return_value=None
            ), mock.patch.object(start_server, "send_discord_message"):
                allowed = start_server._startup_recovery_preflight(vcfg)

            self.assertFalse(allowed)
            self.assertFalse((vcfg.save_dir / "Server.vns").exists())

    def test_disabled_recovery_does_not_touch_missing_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vcfg = self._recovery_config(root, enabled=False)
            self._save_archive(root / "Backups" / "Crash" / "Server_Crash.zip", b"safe")

            with mock.patch.object(start_server, "recover_missing_save") as recover:
                self.assertTrue(start_server._startup_recovery_preflight(vcfg))

            recover.assert_not_called()

    def test_failed_recovery_blocks_update_monitors_and_server_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vcfg = self._recovery_config(root)
            vcfg.selected_exe = root / "Server" / "VeinServer.exe"
            vcfg.raw["extra_launch_args"] = []
            vcfg.runtime_dir.mkdir(parents=True)

            with mock.patch.object(
                start_server, "load_and_validate_config", return_value=vcfg
            ), mock.patch.object(
                start_server, "find_running_server", return_value=None
            ), mock.patch.object(
                start_server, "_startup_recovery_preflight", return_value=False
            ), mock.patch.object(
                start_server, "_steam_update_if_enabled"
            ) as update, mock.patch.object(
                start_server, "_start_monitors"
            ) as monitors, mock.patch.object(
                start_server, "start_vein_server"
            ) as launch, mock.patch.object(
                start_server, "send_discord_message"
            ), mock.patch.object(
                start_server, "set_server_state"
            ), mock.patch.object(
                start_server, "create_startup_lock"
            ), mock.patch.object(
                start_server, "clear_startup_lock"
            ), mock.patch.object(
                start_server, "RUNTIME_DIR", vcfg.runtime_dir
            ), mock.patch.object(
                start_server, "RESTARTING_LOCK", vcfg.runtime_dir / "restart.lock"
            ):
                result = start_server.main()

            self.assertEqual(result, 1)
            update.assert_not_called()
            monitors.assert_not_called()
            launch.assert_not_called()

    def test_existing_server_prevents_duplicate_launch_and_update(self) -> None:
        existing = mock.Mock(pid=4321)
        existing.name.return_value = "VeinServer-Win64-Test.exe"
        vcfg = SimpleNamespace(
            server_dir=ROOT / "Server",
            runtime_dir=ROOT / "Runtime",
            selected_exe=ROOT / "Server" / "Vein" / "Binaries" / "Win64" / "VeinServer.exe",
            server_executables=[
                "Vein/Binaries/Win64/VeinServer.exe",
                "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
            ],
            raw={},
        )

        with mock.patch.object(start_server, "load_and_validate_config", return_value=vcfg), mock.patch.object(
            start_server, "find_running_server", return_value=existing
        ) as find, mock.patch.object(start_server, "set_server_state") as set_state, mock.patch.object(
            start_server, "_steam_update_if_enabled"
        ) as update, mock.patch.object(start_server, "start_vein_server") as launch, mock.patch.object(
            start_server, "send_discord_message"
        ) as send:
            result = start_server.main()

        self.assertEqual(result, 0)
        find.assert_called_once_with(
            executable_names=["VeinServer.exe", "VeinServer-Win64-Test.exe"],
            server_dir=vcfg.server_dir,
        )
        set_state.assert_called_once()
        update.assert_not_called()
        launch.assert_not_called()
        self.assertIn("already running", send.call_args.args[0])

    def test_failed_launch_stops_partially_started_monitors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "Runtime"
            runtime.mkdir()
            (runtime / "log_monitor.pid").write_text("123", encoding="utf-8")
            selected = root / "Server" / "VeinServer.exe"
            selected.parent.mkdir(parents=True)
            selected.write_bytes(b"fixture")
            vcfg = SimpleNamespace(
                server_dir=selected.parent,
                runtime_dir=runtime,
                selected_exe=selected,
                server_executables=[selected.name],
                raw={"extra_launch_args": [], "monitor": {"startup_quiet_seconds": 0}},
            )

            with mock.patch.object(
                start_server, "load_and_validate_config", return_value=vcfg
            ), mock.patch.object(
                start_server, "find_running_server", return_value=None
            ), mock.patch.object(
                start_server, "_startup_recovery_preflight", return_value=True
            ), mock.patch.object(
                start_server, "_steam_update_if_enabled"
            ), mock.patch.object(
                start_server, "_start_monitors", return_value=["log"]
            ), mock.patch.object(
                start_server, "start_vein_server", return_value=None
            ), mock.patch.object(
                start_server, "stop_log_monitor"
            ) as stop_log, mock.patch.object(
                start_server, "stop_crash_monitor"
            ) as stop_crash, mock.patch.object(
                start_server, "send_discord_message"
            ), mock.patch.object(
                start_server, "set_server_state"
            ), mock.patch.object(
                start_server, "create_startup_lock"
            ) as create_lock, mock.patch.object(
                start_server, "clear_startup_lock"
            ) as clear_lock, mock.patch.object(
                start_server, "_clear_restart_lock"
            ) as clear_restart, mock.patch.object(
                start_server, "RUNTIME_DIR", runtime
            ), mock.patch.object(
                start_server, "RESTARTING_LOCK", runtime / "restart.lock"
            ), mock.patch.object(start_server.time, "sleep"):
                result = start_server.main()

        self.assertEqual(result, 1)
        create_lock.assert_called_once_with()
        clear_lock.assert_called_once_with()
        self.assertGreaterEqual(clear_restart.call_count, 1)
        stop_log.assert_called_once_with()
        stop_crash.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
