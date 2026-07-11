from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import update_steam  # noqa: E402


class UpdateSteamTests(unittest.TestCase):
    def test_parse_args_handles_ttl_and_no_cache(self) -> None:
        args = update_steam._parse_args(["--show-versions", "--json", "--ttl", "0", "--no-cache"])

        self.assertTrue(args["show_versions"])
        self.assertTrue(args["json"])
        self.assertEqual(args["ttl"], 0)
        self.assertTrue(args["no_cache"])

        defaults = update_steam._parse_args(["--ttl", "bad"])
        self.assertEqual(defaults["ttl"], 300)

    def test_check_for_steam_update_skips_when_feature_disabled(self) -> None:
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=False):
            self.assertTrue(update_steam.check_for_steam_update())

    def test_check_for_steam_update_skips_when_config_is_missing(self) -> None:
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam,
            "STEAMCMD_PATH",
            "",
        ), mock.patch.object(
            update_steam,
            "APP_ID",
            "",
        ), mock.patch("builtins.print") as printed:
            self.assertIsNone(update_steam.check_for_steam_update())

        printed.assert_called_once()

    def test_check_for_steam_update_runs_steamcmd_success(self) -> None:
        proc = mock.Mock(returncode=1, stdout="Success! App '123' fully installed")
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam,
            "STEAMCMD_PATH",
            "steamcmd.exe",
        ), mock.patch.object(
            update_steam,
            "APP_ID",
            "123",
        ), mock.patch.object(
            update_steam,
            "SERVER_DIR",
            Path("."),
        ), mock.patch.dict(
            update_steam.config,
            {"steam_update_retries": 0, "steam_update_timeout_seconds": 1},
            clear=False,
        ), mock.patch.object(
            update_steam.subprocess,
            "run",
            return_value=proc,
        ), mock.patch.object(
            update_steam,
            "send_discord_message",
        ) as send, mock.patch("builtins.print"):
            self.assertTrue(update_steam.check_for_steam_update())

        send.assert_called_once()

    def test_check_for_steam_update_skips_missing_absolute_executable(self) -> None:
        missing = ROOT / "missing-steamcmd" / "steamcmd.exe"
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam, "STEAMCMD_PATH", str(missing)
        ), mock.patch.object(update_steam, "APP_ID", "123"), mock.patch.object(
            update_steam.subprocess, "run"
        ) as run, mock.patch.object(update_steam, "send_discord_message") as send:
            result = update_steam.check_for_steam_update()

        self.assertIsNone(result)
        run.assert_not_called()
        self.assertIn("not available", send.call_args.args[0])

    def test_check_for_steam_update_builds_beta_validate_args(self) -> None:
        proc = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam,
            "STEAMCMD_PATH",
            "steamcmd.exe",
        ), mock.patch.object(
            update_steam,
            "APP_ID",
            "123",
        ), mock.patch.object(
            update_steam,
            "SERVER_DIR",
            Path("Server"),
        ), mock.patch.dict(
            update_steam.config,
            {
                "steam_update_validate": True,
                "steam_update_beta": "beta",
                "steam_update_beta_password": "secret",
                "steam_update_retries": 0,
                "steam_update_timeout_seconds": 9,
            },
            clear=False,
        ), mock.patch.object(
            update_steam.subprocess,
            "run",
            return_value=proc,
        ) as run, mock.patch.object(
            update_steam,
            "send_discord_message",
        ), mock.patch("builtins.print"):
            self.assertTrue(update_steam.check_for_steam_update())

        cmd = run.call_args.args[0]
        app_update = cmd.index("+app_update")
        self.assertEqual(
            cmd[app_update + 1 : app_update + 7],
            ["123", "-beta", "beta", "-betapassword", "secret", "validate"],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 9)

    def test_check_for_steam_update_retries_failures_and_reports_final_failure(self) -> None:
        proc = mock.Mock(returncode=2, stdout="not installed")
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam,
            "STEAMCMD_PATH",
            "steamcmd.exe",
        ), mock.patch.object(
            update_steam,
            "APP_ID",
            "123",
        ), mock.patch.object(
            update_steam,
            "SERVER_DIR",
            Path("."),
        ), mock.patch.dict(
            update_steam.config,
            {"steam_update_retries": 1, "steam_update_timeout_seconds": 1},
            clear=False,
        ), mock.patch.object(
            update_steam.subprocess,
            "run",
            return_value=proc,
        ) as run, mock.patch.object(
            update_steam.time,
            "sleep",
        ) as sleep, mock.patch.object(
            update_steam,
            "send_discord_message",
        ) as send, mock.patch("builtins.print"):
            self.assertFalse(update_steam.check_for_steam_update())

        self.assertEqual(run.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        send.assert_called_once_with("SteamCMD update failed after retries.", channel="startup")

    def test_check_for_steam_update_handles_timeout_and_exception(self) -> None:
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=True), mock.patch.object(
            update_steam,
            "STEAMCMD_PATH",
            "steamcmd.exe",
        ), mock.patch.object(
            update_steam,
            "APP_ID",
            "123",
        ), mock.patch.object(
            update_steam,
            "SERVER_DIR",
            Path("."),
        ), mock.patch.dict(
            update_steam.config,
            {"steam_update_retries": 1, "steam_update_timeout_seconds": 1},
            clear=False,
        ), mock.patch.object(
            update_steam.subprocess,
            "run",
            side_effect=[
                update_steam.subprocess.TimeoutExpired(cmd="steamcmd", timeout=1),
                OSError("steamcmd failed"),
            ],
        ), mock.patch.object(
            update_steam.time,
            "sleep",
        ), mock.patch.object(
            update_steam,
            "send_discord_message",
        ), mock.patch("builtins.print"):
            self.assertFalse(update_steam.check_for_steam_update())

    def test_main_invalidates_cache_after_success(self) -> None:
        before = {"installed_buildid": "1", "remote_buildid": "2", "cached": False}
        after = {"installed_buildid": "2", "remote_buildid": "2", "cached": False}
        with mock.patch.dict(update_steam.config, {"app_id": "123", "steam_update_beta": ""}, clear=False), mock.patch.object(
            update_steam,
            "get_versions",
            side_effect=[before, after],
        ), mock.patch.object(
            update_steam,
            "check_for_steam_update",
            return_value=True,
        ), mock.patch.object(
            update_steam,
            "invalidate_cache",
        ) as invalidate, mock.patch("builtins.print"):
            code = update_steam.main(["--no-cache"])

        self.assertEqual(code, 0)
        invalidate.assert_called_once_with("123", "public")

    def test_main_outputs_versions_and_json_success(self) -> None:
        before = {"installed_buildid": "1", "remote_buildid": "2", "cached": True}
        after = {"installed_buildid": "2", "remote_buildid": "2", "cached": False}
        with mock.patch.dict(update_steam.config, {"app_id": "123", "steam_update_beta": "beta"}, clear=False), mock.patch.object(
            update_steam,
            "get_versions",
            side_effect=[before, after],
        ), mock.patch.object(
            update_steam,
            "check_for_steam_update",
            return_value=True,
        ), mock.patch.object(
            update_steam,
            "invalidate_cache",
        ) as invalidate, mock.patch("builtins.print") as printed:
            code = update_steam.main(["--show-versions"])

        self.assertEqual(code, 0)
        invalidate.assert_called_once_with("123", "beta")
        self.assertTrue(any("[Before]" in call.args[0] for call in printed.call_args_list))
        self.assertTrue(any("[After ]" in call.args[0] for call in printed.call_args_list))

        with mock.patch.dict(update_steam.config, {"app_id": "123", "steam_update_beta": ""}, clear=False), mock.patch.object(
            update_steam,
            "get_versions",
            side_effect=[before, after],
        ), mock.patch.object(
            update_steam,
            "check_for_steam_update",
            return_value=True,
        ), mock.patch.object(
            update_steam,
            "invalidate_cache",
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(update_steam.main(["--json"]), 0)

        self.assertTrue(json.loads(printed.call_args.args[0])["ok"])

    def test_main_outputs_failure_plain_and_json_without_invalidating_cache(self) -> None:
        before = {"installed_buildid": "1", "remote_buildid": "2", "cached": False}
        with mock.patch.dict(update_steam.config, {"app_id": "123", "steam_update_beta": ""}, clear=False), mock.patch.object(
            update_steam,
            "get_versions",
            return_value=before,
        ), mock.patch.object(
            update_steam,
            "check_for_steam_update",
            return_value=False,
        ), mock.patch.object(
            update_steam,
            "invalidate_cache",
        ) as invalidate, mock.patch("builtins.print") as printed:
            self.assertEqual(update_steam.main([]), 1)

        invalidate.assert_not_called()
        printed.assert_any_call("[Update] FAILED")

        with mock.patch.dict(update_steam.config, {"app_id": "123", "steam_update_beta": ""}, clear=False), mock.patch.object(
            update_steam,
            "get_versions",
            return_value=before,
        ), mock.patch.object(
            update_steam,
            "check_for_steam_update",
            return_value=False,
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(update_steam.main(["--json"]), 1)

        payload = json.loads(printed.call_args.args[0])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "update_failed")


if __name__ == "__main__":
    unittest.main()
