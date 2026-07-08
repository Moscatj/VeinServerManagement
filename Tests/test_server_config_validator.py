from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import server_config_validator as validator  # noqa: E402


class ServerConfigValidatorTests(unittest.TestCase):
    def _server_root(self, base: Path) -> Path:
        root = base / "Server"
        win64 = root / "Vein" / "Binaries" / "Win64"
        config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
        win64.mkdir(parents=True)
        config_dir.mkdir(parents=True)
        (win64 / "VeinServer.exe").write_text("exe", encoding="utf-8")
        (win64 / "steam_api64.dll").write_text("dll", encoding="utf-8")
        return root

    def _config(self, root: Path) -> dict[str, object]:
        return {
            "server_dir": str(root),
            "server_executables": ["Vein/Binaries/Win64/VeinServer.exe"],
            "game_port": 7777,
            "query_port": 27015,
            "max_players": 8,
            "http_api": {"enabled": True, "port": 8080},
        }

    def test_read_unreal_ini_preserves_duplicate_plus_keys(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "Game.ini"
            path.write_text(
                "[/Script/Vein.VeinGameSession]\n"
                "+AdminSteamIDs=111\n"
                "+AdminSteamIDs=222\n"
                "ServerName=\"Test Server\"\n",
                encoding="utf-8",
            )

            sections = validator.read_unreal_ini(path)

        self.assertEqual(
            sections["/Script/Vein.VeinGameSession"]["AdminSteamIDs"],
            ["111", "222"],
        )
        self.assertEqual(sections["/Script/Vein.VeinGameSession"]["ServerName"], ["Test Server"])

    def test_validate_server_config_passes_complete_install(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            (config_dir / "Game.ini").write_text(
                "[/Script/Engine.GameSession]\n"
                "MaxPlayers=8\n"
                "[/Script/Vein.VeinGameSession]\n"
                "HTTPPort=8080\n"
                "ServerName=Local Test\n"
                "+AdminSteamIDs=123\n"
                "[OnlineSubsystemSteam]\n"
                "GameServerQueryPort=27015\n"
                "[URL]\n"
                "Port=7777\n",
                encoding="utf-8",
            )
            (config_dir / "Engine.ini").write_text(
                "[Core.Log]\nLogOnline=Warning\n",
                encoding="utf-8",
            )

            results = validator.validate_server_config(self._config(root))

        statuses = {result.name: result.status for result in results}
        self.assertEqual(statuses["server.install.executable"], "PASS")
        self.assertEqual(statuses["server.install.steam_api64"], "PASS")
        self.assertEqual(statuses["server.config.http_port"], "PASS")
        self.assertEqual(statuses["server.config.game_port"], "PASS")
        self.assertEqual(statuses["server.config.query_port"], "PASS")
        self.assertEqual(statuses["server.config.max_players"], "PASS")
        self.assertFalse(any(result.status == "FAIL" for result in results))

    def test_validate_server_config_warns_for_mismatched_ports_and_missing_admins(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            (config_dir / "Game.ini").write_text(
                "[/Script/Engine.GameSession]\n"
                "MaxPlayers=16\n"
                "[/Script/Vein.VeinGameSession]\n"
                "HTTPPort=9000\n"
                "[OnlineSubsystemSteam]\n"
                "GameServerQueryPort=27016\n"
                "[URL]\n"
                "Port=7778\n",
                encoding="utf-8",
            )

            results = validator.validate_server_config(self._config(root))

        statuses = {result.name: result.status for result in results}
        self.assertEqual(statuses["server.config.http_port"], "WARN")
        self.assertEqual(statuses["server.config.game_port"], "WARN")
        self.assertEqual(statuses["server.config.query_port"], "WARN")
        self.assertEqual(statuses["server.config.max_players"], "WARN")
        self.assertEqual(statuses["server.config.admins"], "WARN")
        self.assertEqual(statuses["server.config.engine_ini"], "WARN")

    def test_optional_core_log_noise_controls_are_info(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            (config_dir / "Game.ini").write_text(
                "[/Script/Engine.GameSession]\n"
                "MaxPlayers=8\n"
                "[/Script/Vein.VeinGameSession]\n"
                "HTTPPort=8080\n"
                "ServerName=Local Test\n"
                "+AdminSteamIDs=123\n"
                "[OnlineSubsystemSteam]\n"
                "GameServerQueryPort=27015\n"
                "[URL]\n"
                "Port=7777\n",
                encoding="utf-8",
            )
            (config_dir / "Engine.ini").write_text("[ConsoleVariables]\nvein.PvP=True\n", encoding="utf-8")

            results = validator.validate_server_config(self._config(root))

        statuses = {result.name: result.status for result in results}
        self.assertEqual(statuses["server.config.core_log"], "INFO")
        self.assertEqual(validator.summarize(results)["INFO"], 1)

    def test_main_emits_json_without_failures(self) -> None:
        result = validator.ServerConfigCheck("example", "WARN", "check this")
        with mock.patch.object(validator, "validate_server_config", return_value=[result]), mock.patch(
            "config.load_config",
            return_value={},
        ), mock.patch("builtins.print") as printed:
            code = validator.main(["--json"])

        self.assertEqual(code, 0)
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload["summary"]["WARN"], 1)
        self.assertEqual(payload["summary"]["INFO"], 0)


if __name__ == "__main__":
    unittest.main()
