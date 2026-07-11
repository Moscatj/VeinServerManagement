from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

os.environ.setdefault("VEIN_CONFIG", str(ROOT / "Config" / "config.example.yaml"))

import start_server  # noqa: E402


class StartServerOrchestrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
