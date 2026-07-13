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

from Tools.server_config_validator import (  # noqa: E402
    ENGINE_GAME_SESSION_SECTION,
    GAME_INI_SECTION,
    ONLINE_STEAM_SECTION,
    URL_SECTION,
)
from Tools.server_config_preview import GAME_STATE_SECTION, SERVER_SETTINGS_SECTION  # noqa: E402
from Tools.server_quickstart import (  # noqa: E402
    apply_quick_start_plan,
    build_quick_start_plan,
    inspect_server_root,
    load_existing_server_settings,
    ServerRootInspection,
)


def _sample_discord_webhook() -> str:
    return "https://discord.com/api/" + "webhooks/1/token"


class ServerQuickStartTests(unittest.TestCase):
    @staticmethod
    def _existing_server(base: Path) -> tuple[Path, Path]:
        server_root = base / "Server"
        win64 = server_root / "Vein" / "Binaries" / "Win64"
        win64.mkdir(parents=True)
        (win64 / "VeinServer.exe").write_text("", encoding="utf-8")
        config_dir = server_root / "Vein" / "Saved" / "Config" / "WindowsServer"
        config_dir.mkdir(parents=True)
        return server_root, config_dir

    def test_build_quick_start_plan_uses_app_managed_defaults(self) -> None:
        with mock.patch(
            "Tools.server_quickstart.inspect_server_root",
            return_value=ServerRootInspection("missing", "Server", ()),
        ):
            plan = build_quick_start_plan({"server_name": "Community Server"})

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.config_updates["paths"]["server_root"], "Server")
        self.assertNotIn("saves_dir", plan.config_updates["paths"])
        self.assertEqual(plan.config_updates["save_games"]["override"], "")
        self.assertNotIn("logs_dir", plan.config_updates["paths"])
        self.assertNotIn("absolute_log_file", plan.config_updates["paths"])
        self.assertEqual(plan.config_updates["game_log"]["override"], "")
        self.assertEqual(plan.config_updates["steam"]["steamcmd_path"], "SteamCMD/steamcmd.exe")
        self.assertEqual(plan.config_updates["server"]["game_port"], 7777)
        self.assertEqual(plan.config_updates["server"]["query_port"], 27015)
        self.assertEqual(
            plan.config_updates["server"]["preferred_exe"],
            "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
        )
        self.assertEqual(
            plan.config_updates["server"]["executables"][0],
            "Vein/Binaries/Win64/VeinServer-Win64-Test.exe",
        )
        self.assertEqual(plan.config_updates["server"]["ports"]["game"], 7777)
        self.assertEqual(plan.config_updates["server"]["ports"]["query"], 27015)
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

        errors = {(issue.field, issue.severity) for issue in plan.issues}
        self.assertIn(("server_root", "ERROR"), errors)
        self.assertFalse(plan.can_apply)

    def test_new_server_mode_rejects_occupied_destination(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Destination"
            root.mkdir()
            (root / "unrelated.txt").write_text("occupied", encoding="utf-8")

            plan = build_quick_start_plan(
                {"server_root": str(root), "server_name": "New Server"}
            )

        self.assertFalse(plan.can_apply)
        self.assertTrue(any("missing or empty" in issue.message for issue in plan.issues))

    def test_server_root_inspection_detects_ini_only_partial_install(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Server"
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            config_dir.mkdir(parents=True)
            (config_dir / "Game.ini").write_text("[URL]\nPort=7777\n", encoding="utf-8")

            inspection = inspect_server_root(root)
            settings = load_existing_server_settings(root)

        self.assertTrue(inspection.is_existing_server)
        self.assertEqual(settings.values["game_port"], 7777)

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
        with mock.patch(
            "Tools.server_quickstart.inspect_server_root",
            return_value=ServerRootInspection("missing", "Server", ()),
        ):
            plan = build_quick_start_plan({"server_name": "Serializable"})
        payload = plan.as_dict()

        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["config_updates"]["paths"]["server_root"], "Server")
        self.assertTrue(payload["server_config_edits"])
        self.assertTrue(all("source" in edit for edit in payload["server_config_edits"]))

    def test_apply_quick_start_plan_writes_management_config_and_skips_missing_server_root(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = base / "config.yaml"
            cfg.write_text("version: '2.2'\npaths:\n  runtime_dir: Runtime\n", encoding="utf-8")

            result = apply_quick_start_plan(
                {
                    "server_name": "New Server",
                    "server_root": str(base / "MissingServer"),
                    "http_api_enabled": False,
                },
                config_path=cfg,
                config_backup_root=base / "config-backups",
                server_config_backup_root=base / "server-backups",
            )

            text = cfg.read_text(encoding="utf-8")
            self.assertTrue(result.config_changed)
            self.assertFalse(result.server_config_applied)
            self.assertTrue(result.messages)
            self.assertIn("New Server", text)
            self.assertIn("MissingServer", text)
            self.assertTrue(Path(result.config_backup).exists())
            self.assertFalse((base / "MissingServer" / "Vein").exists())

    def test_apply_quick_start_plan_migrates_legacy_game_log_paths(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = base / "config.yaml"
            cfg.write_text(
                "\n".join(
                    [
                        "version: '2.2'",
                        "paths:",
                        "  runtime_dir: Runtime",
                        "  logs_dir: OldLogs",
                        "  absolute_log_file: OldLogs/Vein.log",
                        "  saves_dir: OldSaves",
                        "logs_dir: OlderLogs",
                        "absolute_log_file: OlderLogs/Vein.log",
                        "save_dir: OlderSaves",
                    ]
                ),
                encoding="utf-8",
            )

            apply_quick_start_plan(
                {
                    "server_name": "Migrated Server",
                    "server_root": str(base / "MissingServer"),
                    "game_log_override": "",
                    "http_api_enabled": False,
                },
                config_path=cfg,
                config_backup_root=base / "config-backups",
            )

            text = cfg.read_text(encoding="utf-8")

        self.assertIn("game_log:", text)
        self.assertIn("override: ''", text)
        self.assertNotIn("logs_dir:", text)
        self.assertNotIn("absolute_log_file:", text)
        self.assertNotIn("saves_dir:", text)
        self.assertNotIn("save_dir:", text)
        self.assertIn("save_games:", text)

    def test_build_quick_start_plan_keeps_advanced_game_log_override(self) -> None:
        plan = build_quick_start_plan(
            {
                "server_name": "Override Server",
                "game_log_override": "D:/VeinLogs/Custom.log",
            }
        )

        self.assertEqual(
            plan.config_updates["game_log"]["override"],
            "D:/VeinLogs/Custom.log",
        )

    def test_build_quick_start_plan_keeps_advanced_save_games_override(self) -> None:
        plan = build_quick_start_plan(
            {
                "server_name": "Override Server",
                "save_games_override": "D:/VeinWorlds/SaveGames",
            }
        )

        self.assertEqual(
            plan.config_updates["save_games"]["override"],
            "D:/VeinWorlds/SaveGames",
        )

    def test_apply_quick_start_plan_applies_guarded_server_config_when_root_exists(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            server_root = base / "Server"
            win64 = server_root / "Vein" / "Binaries" / "Win64"
            win64.mkdir(parents=True)
            (win64 / "VeinServer.exe").write_text("", encoding="utf-8")
            (win64 / "steam_api64.dll").write_text("", encoding="utf-8")
            config_dir = server_root / "Vein" / "Saved" / "Config" / "WindowsServer"
            config_dir.mkdir(parents=True)
            (config_dir / "Game.ini").write_text("[/Script/Vein.VeinGameSession]\nServerName=Old\n", encoding="utf-8")
            (config_dir / "Engine.ini").write_text("[ConsoleVariables]\nvein.PvP=True\n", encoding="utf-8")
            cfg = base / "config.yaml"

            result = apply_quick_start_plan(
                {
                    "setup_mode": "existing",
                    "existing_loaded_root": str(server_root),
                    "server_config_fields": ["server_name", "max_players"],
                    "server_name": "Applied Server",
                    "server_root": str(server_root),
                    "max_players": 10,
                    "http_api_enabled": False,
                },
                config_path=cfg,
                config_backup_root=base / "config-backups",
                server_config_backup_root=base / "server-backups",
            )

            game_text = (config_dir / "Game.ini").read_text(encoding="utf-8")
            self.assertTrue(result.server_config_applied)
            self.assertIn("ServerName=Applied Server", game_text)
            self.assertIn("MaxPlayers=10", game_text)
            self.assertTrue(result.server_config_result)
            self.assertTrue(result.server_config_result["backups"])
            self.assertTrue(Path(result.server_config_result["backups"][0]).exists())

    def test_load_existing_server_settings_reads_supported_non_secret_values(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_root, config_dir = self._existing_server(Path(tmp))
            (config_dir / "Game.ini").write_text(
                "\n".join(
                    [
                        "[/Script/Engine.GameSession]",
                        "MaxPlayers=14",
                        "",
                        "[/Script/Vein.VeinGameSession]",
                        "ServerName=Imported Server",
                        "Password=do-not-import",
                        "+AdminSteamIDs=111",
                        "+AdminSteamIDs=222",
                        "",
                        f"[{SERVER_SETTINGS_SECTION}]",
                        f'DiscordChatWebhookURL="{_sample_discord_webhook()}"',
                        "",
                        "[URL]",
                        "Port=7788",
                    ]
                ),
                encoding="utf-8",
            )
            (config_dir / "Engine.ini").write_text(
                "[ConsoleVariables]\nvein.PvP=False\n",
                encoding="utf-8",
            )

            settings = load_existing_server_settings(server_root)

            self.assertEqual(settings.values["server_name"], "Imported Server")
            self.assertEqual(settings.values["max_players"], 14)
            self.assertEqual(settings.values["game_port"], 7788)
            self.assertFalse(settings.values["pvp_enabled"])
            self.assertEqual(settings.values["admin_steam_ids"], ["111", "222"])
            self.assertNotIn("password", settings.values)
            self.assertTrue(settings.password_configured)
            self.assertTrue(settings.discord_chat_webhook_configured)
            self.assertFalse(settings.discord_admin_webhook_configured)
            self.assertNotIn("discord_chat_webhook_url", settings.values)
            self.assertEqual(settings.missing_files, ())

    def test_load_existing_server_settings_reports_no_password(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_root, config_dir = self._existing_server(Path(tmp))
            (config_dir / "Game.ini").write_text(
                "[/Script/Vein.VeinGameSession]\nServerName=No Password\n",
                encoding="utf-8",
            )

            settings = load_existing_server_settings(server_root)

        self.assertFalse(settings.password_configured)
        self.assertNotIn("password", settings.values)

    def test_existing_mode_only_emits_fields_changed_after_import(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_root, config_dir = self._existing_server(Path(tmp))
            (config_dir / "Game.ini").write_text(
                "[/Script/Vein.VeinGameSession]\nServerName=Old Name\nMaxPlayers=8\n",
                encoding="utf-8",
            )
            (config_dir / "Engine.ini").write_text("[ConsoleVariables]\nvein.PvP=True\n", encoding="utf-8")

            plan = build_quick_start_plan(
                {
                    "setup_mode": "existing",
                    "existing_loaded_root": str(server_root),
                    "server_root": str(server_root),
                    "server_name": "New Name",
                    "max_players": 20,
                    "server_config_fields": ["server_name"],
                }
            )

            keys = {(edit.source, edit.key) for edit in plan.server_config_edits}
            self.assertTrue(plan.can_apply)
            self.assertEqual(keys, {("Game.ini", "ServerName")})

    def test_existing_mode_requires_loaded_matching_server_root(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_root, _ = self._existing_server(Path(tmp))
            plan = build_quick_start_plan(
                {
                    "setup_mode": "existing",
                    "server_root": str(server_root),
                    "server_name": "Existing",
                }
            )

            self.assertFalse(plan.can_apply)
            self.assertTrue(any("Load settings" in issue.message for issue in plan.issues))


if __name__ == "__main__":
    unittest.main()
