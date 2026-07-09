from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.server_config_validator import (  # noqa: E402
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
)
from Tools.server_config_preview import GAME_STATE_SECTION, SERVER_SETTINGS_SECTION  # noqa: E402
from Tools.server_quickstart import build_quick_start_plan  # noqa: E402


def _sample_discord_webhook() -> str:
    return "https://discord.com/api/" + "webhooks/1/token"


class ServerQuickStartTests(unittest.TestCase):
    def test_build_quick_start_plan_uses_app_managed_defaults(self) -> None:
        plan = build_quick_start_plan({"server_name": "Community Server"})

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.config_updates["paths"]["server_root"], "Server")
        self.assertEqual(plan.config_updates["paths"]["saves_dir"], "Server/Vein/Saved/SaveGames")
        self.assertEqual(plan.config_updates["paths"]["logs_dir"], "Server/Vein/Saved/Logs")
        self.assertEqual(plan.config_updates["steam"]["steamcmd_path"], "SteamCMD/steamcmd.exe")
        self.assertEqual(plan.config_updates["server"]["game_port"], 7777)
        self.assertEqual(plan.config_updates["server"]["query_port"], 27015)
        self.assertEqual(plan.config_updates["server"]["max_players"], 8)
        self.assertEqual(plan.config_updates["server"]["multi_home_ip"], "0.0.0.0")
        self.assertIn("-log", plan.config_updates["server"]["extra_launch_args"])
        self.assertEqual(plan.config_updates["discord"]["defaults"]["server_name"], "Community Server")
        self.assertIn(("http_api", "WARN"), {(issue.field, issue.severity) for issue in plan.issues})

    def test_build_quick_start_plan_requires_server_name_and_valid_ports(self) -> None:
        plan = build_quick_start_plan(
            {
                "server_name": "",
                "game_port": 0,
                "query_port": 70000,
                "http_port": "bad",
                "max_players": -1,
            }
        )

        self.assertFalse(plan.can_apply)
        errors = {(issue.field, issue.severity) for issue in plan.issues}
        self.assertIn(("server_name", "ERROR"), errors)
        self.assertIn(("game_port", "ERROR"), errors)
        self.assertIn(("query_port", "ERROR"), errors)
        self.assertIn(("http_port", "ERROR"), errors)
        self.assertIn(("max_players", "ERROR"), errors)

    def test_build_quick_start_plan_detects_existing_server_executable(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Server"
            exe = root / "Vein" / "Binaries" / "Win64" / "VeinServer.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")

            plan = build_quick_start_plan(
                {
                    "server_root": str(root),
                    "server_name": "Existing Server",
                }
            )

        warnings = {(issue.field, issue.severity) for issue in plan.issues}
        self.assertNotIn(("server_executables", "WARN"), warnings)
        self.assertTrue(plan.can_apply)

    def test_build_quick_start_plan_generates_expected_ini_edits(self) -> None:
        plan = build_quick_start_plan(
            {
                "server_name": "Configured Server",
                "server_description": "Testing",
                "password": "joinpass",
                "public": False,
                "max_players": 12,
                "game_port": 7779,
                "query_port": 27019,
                "http_port": 8090,
                "admin_steam_ids": ["111", "222"],
                "super_admin_steam_ids": ["333"],
                "whitelisted_players": ["444"],
                "pvp_enabled": False,
                "bind_addr": "127.0.0.1",
                "vac_enabled": True,
                "heartbeat_interval": 10,
                "show_scoreboard_badges": False,
                "discord_chat_webhook_url": _sample_discord_webhook(),
            }
        )

        edits = {(edit.source, edit.section, edit.key): edit.values for edit in plan.server_config_edits}
        self.assertEqual(edits[("Game.ini", ENGINE_GAME_SESSION_SECTION, "MaxPlayers")], ("12",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "ServerName")], ("Configured Server",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "ServerDescription")], ("Testing",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "Password")], ("joinpass",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "bPublic")], ("False",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "BindAddr")], ("127.0.0.1",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "HeartbeatInterval")], ("10",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "HTTPPort")], ("8090",))
        self.assertEqual(edits[("Game.ini", ONLINE_STEAM_SECTION, "GameServerQueryPort")], ("27019",))
        self.assertEqual(edits[("Game.ini", ONLINE_STEAM_SECTION, "bVACEnabled")], ("1",))
        self.assertEqual(edits[("Game.ini", URL_SECTION, "Port")], ("7779",))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "AdminSteamIDs")], ("111", "222"))
        self.assertEqual(edits[("Game.ini", GAME_INI_SECTION, "SuperAdminSteamIDs")], ("333",))
        self.assertEqual(edits[("Game.ini", GAME_STATE_SECTION, "WhitelistedPlayers")], ("444",))
        self.assertEqual(edits[("Game.ini", SERVER_SETTINGS_SECTION, "GS_ShowScoreboardBadges")], ("0",))
        self.assertEqual(
            edits[("Game.ini", SERVER_SETTINGS_SECTION, "DiscordChatWebhookURL")],
            (f'"{_sample_discord_webhook()}"',),
        )
        self.assertEqual(edits[("Engine.ini", "ConsoleVariables", "vein.PvP")], ("False",))

    def test_build_quick_start_plan_rejects_env_webhook_for_game_ini(self) -> None:
        plan = build_quick_start_plan(
            {
                "server_name": "Webhook Test",
                "discord_chat_webhook_url": "ENV:DISCORD_WEBHOOK_URL",
            }
        )

        self.assertFalse(plan.can_apply)
        self.assertIn(
            ("discord_chat_webhook_url", "ERROR"),
            {(issue.field, issue.severity) for issue in plan.issues},
        )

    def test_build_quick_start_plan_serializes_to_dict(self) -> None:
        plan = build_quick_start_plan({"server_name": "Serializable"})
        payload = plan.as_dict()

        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["config_updates"]["paths"]["server_root"], "Server")
        self.assertTrue(payload["server_config_edits"])
        self.assertTrue(all("source" in edit for edit in payload["server_config_edits"]))


if __name__ == "__main__":
    unittest.main()
