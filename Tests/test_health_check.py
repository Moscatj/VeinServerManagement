from __future__ import annotations

import json
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import health_check  # noqa: E402


class HealthCheckTests(unittest.TestCase):
    def _base_config(self, root: Path) -> dict[str, object]:
        server_root = root / "server"
        runtime = root / "Runtime"
        logs = root / "Logs"
        backups = root / "Backups"
        saves = server_root / "Vein" / "Saved" / "SaveGames"
        game_logs = server_root / "Vein" / "Saved" / "Logs"
        exe_dir = server_root / "Vein" / "Binaries" / "Win64"

        for folder in (runtime, logs, backups, saves, game_logs, exe_dir):
            folder.mkdir(parents=True)
        (game_logs / "Vein.log").write_text("ok", encoding="utf-8")
        (exe_dir / "VeinServer.exe").write_text("exe", encoding="utf-8")

        return {
            "server_dir": str(server_root),
            "server_executables": ["Vein/Binaries/Win64/VeinServer.exe"],
            "runtime_dir": str(runtime),
            "mgmt_log_dir": str(logs),
            "backup_root": str(backups),
            "save_dir": str(saves),
            "logs_dir": str(game_logs),
            "absolute_log_file": str(game_logs / "Vein.log"),
            "steamcmd_path": "",
            "discord_webhook": "",
        }

    def test_run_health_checks_detects_clean_local_config_with_warnings(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = self._base_config(Path(tmp))
            raw_cfg = {"discord": {"webhooks": {"default": "ENV:DISCORD_WEBHOOK_URL"}}}
            with mock.patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.invalid/webhook"}):
                results = health_check.run_health_checks(cfg=cfg, raw_cfg=raw_cfg)

        statuses = {result.name: result.status for result in results}
        self.assertEqual(statuses["config.load"], "PASS")
        self.assertEqual(statuses["paths.server_root"], "PASS")
        self.assertEqual(statuses["server.executable"], "PASS")
        self.assertEqual(statuses["discord.webhooks"], "PASS")
        self.assertEqual(statuses["steam.steamcmd"], "WARN")
        self.assertFalse(any(result.status == "FAIL" for result in results))

    def test_raw_discord_webhook_is_a_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = self._base_config(Path(tmp))
            raw_webhook = "https://discord.com/api/" + "webhooks/123/secret"
            raw_cfg = {
                "discord": {
                    "webhooks": {
                        "default": raw_webhook
                    }
                }
            }
            results = health_check.run_health_checks(cfg=cfg, raw_cfg=raw_cfg)

        discord = [result for result in results if result.name == "discord.webhooks"][0]
        self.assertEqual(discord.status, "FAIL")
        self.assertIn("Raw Discord webhook URL", discord.message)

    def test_missing_required_directory_fails(self) -> None:
        result = health_check._check_directory(
            "paths.server_root",
            ROOT / "missing-health-check-dir",
            required=True,
        )

        self.assertEqual(result.status, "FAIL")
        self.assertIn("does not exist", result.message)

    def test_missing_optional_file_warns(self) -> None:
        result = health_check._check_file(
            "paths.absolute_log_file",
            ROOT / "missing-health-check.log",
        )

        self.assertEqual(result.status, "WARN")
        self.assertIn("does not exist", result.message)

    def test_raw_config_loader_handles_json_and_missing_files(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text('{"discord": {"enabled": true}}', encoding="utf-8")

            self.assertEqual(
                health_check._load_raw_config(config_path),
                {"discord": {"enabled": True}},
            )
            self.assertEqual(health_check._load_raw_config(Path(tmp) / "missing.yaml"), {})

    def test_config_load_failure_is_reported(self) -> None:
        with mock.patch("config.load_config", side_effect=ValueError("bad config")):
            cfg, result = health_check.check_config_load()

        self.assertEqual(cfg, {})
        self.assertEqual(result.status, "FAIL")
        self.assertIn("bad config", result.message)

    def test_server_executable_warns_when_no_candidate_exists(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            cfg = {
                "server_dir": str(root),
                "server_executables": ["Vein/Binaries/Win64/Nope.exe"],
            }

            result = health_check.check_server_executable(cfg)

        self.assertEqual(result.status, "WARN")
        self.assertIn("No configured server executable", result.message)

    def test_steamcmd_existing_path_passes(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            steamcmd = Path(tmp) / "steamcmd.exe"
            steamcmd.write_text("exe", encoding="utf-8")

            result = health_check.check_steamcmd({"steamcmd_path": str(steamcmd)})

        self.assertEqual(result.status, "PASS")

    def test_steamcmd_missing_path_passes_when_steam_updates_disabled(self) -> None:
        result = health_check.check_steamcmd(
            {
                "steamcmd_path": "",
                "features": {"enable_steam_update": False},
            }
        )

        self.assertEqual(result.status, "PASS")
        self.assertIn("disabled", result.message)

    def test_steamcmd_missing_path_passes_when_startup_updates_disabled(self) -> None:
        result = health_check.check_steamcmd(
            {
                "steamcmd_path": "",
                "auto_update_on_start": False,
            }
        )

        self.assertEqual(result.status, "PASS")
        self.assertIn("startup Steam updates are disabled", result.message)

    def test_json_main_reports_failures_with_nonzero_exit(self) -> None:
        result = health_check.HealthCheckResult("example", "FAIL", "bad")
        with mock.patch.object(health_check, "run_health_checks", return_value=[result]), mock.patch(
            "builtins.print"
        ) as printed:
            code = health_check.main(["--json"])

        self.assertEqual(code, 1)
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload["summary"]["FAIL"], 1)
        self.assertEqual(payload["results"][0]["name"], "example")

    def test_text_main_returns_success_when_no_failures(self) -> None:
        result = health_check.HealthCheckResult("example", "WARN", "check this")
        with mock.patch.object(health_check, "run_health_checks", return_value=[result]), mock.patch(
            "builtins.print"
        ) as printed:
            code = health_check.main([])

        self.assertEqual(code, 0)
        self.assertIn("[WARN] example", printed.call_args.args[0])

    def test_within_repo_boundary_helper(self) -> None:
        self.assertTrue(health_check._is_within(ROOT / "Runtime", ROOT))
        self.assertFalse(health_check._is_within(ROOT.parent, ROOT))

    def test_controller_entrypoint_exports_tool_main(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "health_check_entrypoint_for_test",
            CTRL / "health_check.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertIs(module.main, health_check.main)


if __name__ == "__main__":
    unittest.main()
