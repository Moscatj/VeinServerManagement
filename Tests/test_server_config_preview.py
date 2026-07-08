from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import server_config_preview as preview  # noqa: E402


def _sample_discord_webhook() -> str:
    return "https://discord.com/api/" + "webhooks/1/token"


class ServerConfigPreviewTests(unittest.TestCase):
    def _server_root(self, base: Path) -> Path:
        root = base / "Server"
        config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
        config_dir.mkdir(parents=True)
        return root

    def test_mask_config_value_hides_secrets(self) -> None:
        self.assertEqual(preview.mask_config_value("Password", "secret"), "<configured, masked>")
        self.assertEqual(preview.mask_config_value("ApiToken", "abc"), "<configured, masked>")
        self.assertEqual(
            preview.mask_config_value("DiscordChatWebhookURL", _sample_discord_webhook()),
            "<configured, masked>",
        )
        self.assertEqual(preview.mask_config_value("ServerName", "Local"), "Local")

    def test_build_server_config_preview_extracts_documented_values(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            (config_dir / "Game.ini").write_text(
                "[/Script/Engine.GameSession]\n"
                "MaxPlayers=8\n"
                "[/Script/Vein.VeinGameSession]\n"
                "ServerName=Local Test\n"
                "Password=secret\n"
                "+AdminSteamIDs=111\n"
                "+AdminSteamIDs=222\n"
                "HTTPPort=8080\n"
                "CustomActualServerSetting=enabled\n"
                "[OnlineSubsystemSteam]\n"
                "GameServerQueryPort=27015\n"
                "[URL]\n"
                "Port=7777\n"
                "[/Script/Vein.ServerSettings]\n"
                f"DiscordChatWebhookURL=\"{_sample_discord_webhook()}\"\n",
                encoding="utf-8",
            )
            (config_dir / "Engine.ini").write_text(
                "[ConsoleVariables]\n"
                "vein.PvP=True\n"
                "vein.CustomRuntimeSetting=42\n"
                "[Core.Log]\n"
                "LogOnline=Warning\n",
                encoding="utf-8",
            )

            payload = preview.build_server_config_preview({"server_dir": str(root)})

        items = {(item["section"], item["key"]): item for item in payload["items"]}
        self.assertEqual(payload["missing_files"], [])
        self.assertEqual(items[("/Script/Vein.VeinGameSession", "ServerName")]["value"], "Local Test")
        self.assertEqual(items[("/Script/Vein.VeinGameSession", "Password")]["value"], "<configured, masked>")
        self.assertEqual(items[("/Script/Vein.VeinGameSession", "AdminSteamIDs")]["value"], "111, 222")
        self.assertEqual(
            items[("/Script/Vein.ServerSettings", "DiscordChatWebhookURL")]["value"],
            "<configured, masked>",
        )
        self.assertEqual(items[("ConsoleVariables", "vein.PvP")]["value"], "True")
        self.assertEqual(items[("/Script/Vein.VeinGameSession", "CustomActualServerSetting")]["value"], "enabled")
        self.assertEqual(items[("ConsoleVariables", "vein.CustomRuntimeSetting")]["value"], "42")

    def test_build_server_config_preview_reports_missing_files(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))

            payload = preview.build_server_config_preview({"server_dir": str(root)})

        self.assertEqual(len(payload["missing_files"]), 2)
        self.assertTrue(any(item["value"] == "(not set)" for item in payload["items"]))


if __name__ == "__main__":
    unittest.main()
