from __future__ import annotations

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

    def test_check_for_steam_update_skips_when_feature_disabled(self) -> None:
        with mock.patch.object(update_steam, "is_feature_enabled", return_value=False):
            self.assertTrue(update_steam.check_for_steam_update())

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


if __name__ == "__main__":
    unittest.main()
