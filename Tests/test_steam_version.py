from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import steam_version  # noqa: E402


class SteamVersionTests(unittest.TestCase):
    def test_read_installed_buildid_from_manifest(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            manifest = server_dir / "steamapps" / "appmanifest_123.acf"
            manifest.parent.mkdir()
            manifest.write_text('"buildid" "456789"\n', encoding="utf-8")

            buildid = steam_version._read_installed_buildid(server_dir, "123")

        self.assertEqual(buildid, "456789")

    def test_cache_round_trip_and_freshness(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp) / "Runtime"
            with mock.patch.object(steam_version, "_runtime_dir", return_value=runtime), mock.patch.object(
                steam_version.time,
                "time",
                return_value=1_000,
            ):
                steam_version._save_cache("123", "public", "999")
                cache = steam_version._load_cache("123", "public")
                self.assertTrue(steam_version._cache_fresh(cache or {}, ttl=10))

            self.assertEqual(cache["buildid"], "999")
            self.assertEqual(json.loads((runtime / "steam_version_cache_123_public.json").read_text())["app_id"], "123")

    def test_query_remote_buildid_parses_requested_branch(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            steamcmd = Path(tmp) / "steamcmd.exe"
            steamcmd.write_text("", encoding="utf-8")
            output = '''
            "branches"
            {
                "public"
                {
                    "buildid" "111"
                }
                "beta"
                {
                    "buildid" "222"
                }
            }
            '''
            proc = mock.Mock(stdout=output)

            with mock.patch.object(steam_version.subprocess, "run", return_value=proc):
                buildid = steam_version._query_remote_buildid(steamcmd, "123", "beta", 5)

        self.assertEqual(buildid, "222")

    def test_get_version_status_classifies_states(self) -> None:
        cases = [
            ({"installed_buildid": "1", "remote_buildid": "1"}, "Up-to-date", "ok"),
            ({"installed_buildid": "1", "remote_buildid": "2"}, "Update available", "stale"),
            ({"installed_buildid": "1", "remote_buildid": None}, "Partial data", "unknown"),
            ({"installed_buildid": None, "remote_buildid": None}, "Unknown", "unknown"),
        ]
        for payload, status, state in cases:
            with self.subTest(status=status), mock.patch.object(
                steam_version,
                "get_versions",
                return_value={"ok": bool(payload["installed_buildid"] or payload["remote_buildid"]), **payload},
            ):
                result = steam_version.get_version_status()
                self.assertEqual(result["status"], status)
                self.assertEqual(result["state"], state)

    def test_parse_args_bounds_values(self) -> None:
        args = steam_version._parse_args(
            ["--json", "--status", "--branch", "beta", "--timeout", "0", "--ttl", "-1", "--no-cache"]
        )

        self.assertTrue(args["json"])
        self.assertTrue(args["status"])
        self.assertEqual(args["branch"], "beta")
        self.assertEqual(args["timeout"], 1)
        self.assertEqual(args["ttl"], 0)
        self.assertTrue(args["no_cache"])


if __name__ == "__main__":
    unittest.main()
