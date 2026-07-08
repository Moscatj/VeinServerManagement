from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import server_config_editor as editor  # noqa: E402


class ServerConfigEditorTests(unittest.TestCase):
    def _server_root(self, base: Path) -> Path:
        root = base / "Server"
        config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
        win64 = root / "Vein" / "Binaries" / "Win64"
        config_dir.mkdir(parents=True)
        win64.mkdir(parents=True)
        (win64 / "VeinServer.exe").write_text("", encoding="utf-8")
        (win64 / "steam_api64.dll").write_text("", encoding="utf-8")
        return root

    def test_make_edit_rejects_unknown_key_and_multiline_values(self) -> None:
        with self.assertRaises(ValueError):
            editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "Unknown", "x")
        with self.assertRaises(ValueError):
            editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "ServerName", "bad\nvalue")
        with self.assertRaises(ValueError):
            editor.make_edit("Engine.ini", "ConsoleVariables", "vein.PvP", ["True", "False"])

    def test_preview_edits_updates_existing_section_without_writing(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = self._server_root(Path(tmp))
            game_ini = root / "Vein" / "Saved" / "Config" / "WindowsServer" / "Game.ini"
            game_ini.write_text(
                "[/Script/Vein.VeinGameSession]\nServerName=Old\n",
                encoding="utf-8",
            )
            edit = editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "ServerName", "New")

            plan = editor.preview_server_config_edits({"server_dir": str(root)}, [edit])

            self.assertEqual(len(plan.changed_files), 1)
            diff = next(iter(plan.diffs.values()))
            self.assertIn("-ServerName=Old", diff)
            self.assertIn("+ServerName=New", diff)
            self.assertEqual(game_ini.read_text(encoding="utf-8"), "[/Script/Vein.VeinGameSession]\nServerName=Old\n")

    def test_apply_edits_creates_backup_writes_atomically_and_validates(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            root = self._server_root(base)
            config_dir = root / "Vein" / "Saved" / "Config" / "WindowsServer"
            game_ini = config_dir / "Game.ini"
            engine_ini = config_dir / "Engine.ini"
            game_ini.write_text(
                "[/Script/Engine.GameSession]\nMaxPlayers=8\n"
                "[/Script/Vein.VeinGameSession]\nServerName=Old\n"
                "[OnlineSubsystemSteam]\nGameServerQueryPort=27015\n"
                "[URL]\nPort=7777\n",
                encoding="utf-8",
            )
            engine_ini.write_text("[Core.Log]\nLogOnline=Warning\n", encoding="utf-8")
            edits = [
                editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "ServerName", "New"),
                editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "AdminSteamIDs", ["111", "222"]),
                editor.make_edit("Engine.ini", "ConsoleVariables", "vein.PvP", "True"),
            ]

            result = editor.apply_server_config_edits(
                {"server_dir": str(root), "server_executables": ["Vein/Binaries/Win64/VeinServer.exe"]},
                edits,
                backup_root=base / "Backups" / "ConfigEdits",
            )

            updated_game = game_ini.read_text(encoding="utf-8")
            updated_engine = engine_ini.read_text(encoding="utf-8")
            backups_exist = all(Path(path).exists() for path in result.backups)

        self.assertIn("ServerName=New", updated_game)
        self.assertIn("+AdminSteamIDs=111", updated_game)
        self.assertIn("+AdminSteamIDs=222", updated_game)
        self.assertIn("[ConsoleVariables]\nvein.PvP=True", updated_engine)
        self.assertEqual(len(result.backups), 2)
        self.assertTrue(backups_exist)
        self.assertTrue(any(check.name == "server.config.server_name" for check in result.validation))

    def test_apply_noop_does_not_create_backup(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            root = self._server_root(base)
            game_ini = root / "Vein" / "Saved" / "Config" / "WindowsServer" / "Game.ini"
            game_ini.write_text("[/Script/Vein.VeinGameSession]\nServerName=Same\n", encoding="utf-8")
            edit = editor.make_edit("Game.ini", "/Script/Vein.VeinGameSession", "ServerName", "Same")

            result = editor.apply_server_config_edits(
                {"server_dir": str(root)},
                [edit],
                backup_root=base / "Backups" / "ConfigEdits",
            )

        self.assertEqual(result.changed_files, ())
        self.assertEqual(result.backups, ())


if __name__ == "__main__":
    unittest.main()
