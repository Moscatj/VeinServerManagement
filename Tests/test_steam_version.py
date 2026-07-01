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

    def test_read_installed_buildid_handles_missing_unreadable_and_malformed_manifest(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            manifest = server_dir / "steamapps" / "appmanifest_123.acf"
            manifest.parent.mkdir()

            self.assertIsNone(steam_version._read_installed_buildid(server_dir, "123"))

            manifest.write_text('"name" "Vein"\n', encoding="utf-8")
            self.assertIsNone(steam_version._read_installed_buildid(server_dir, "123"))

            with mock.patch.object(Path, "read_text", side_effect=OSError("cannot read")):
                self.assertIsNone(steam_version._read_installed_buildid(server_dir, "123"))

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

    def test_runtime_dir_cache_path_and_cache_failure_paths(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp) / "Runtime"
            with mock.patch.dict(steam_version.config, {"runtime_dir": str(runtime)}, clear=True):
                self.assertEqual(steam_version._runtime_dir(), runtime)

            with mock.patch.dict(steam_version.config, {}, clear=True):
                self.assertEqual(steam_version._runtime_dir().name, "Runtime")

            with mock.patch.object(steam_version, "_runtime_dir", return_value=runtime):
                path = steam_version._cache_path("123", "Beta/Preview")
                self.assertEqual(path.name, "steam_version_cache_123_beta_preview.json")
                path.write_text("not json", encoding="utf-8")
                self.assertIsNone(steam_version._load_cache("123", "Beta/Preview"))

            self.assertFalse(steam_version._cache_fresh({"fetched_at": "bad"}, ttl=10))

            with mock.patch.object(steam_version, "_cache_path", return_value=runtime / "missing" / "cache.json"):
                steam_version._save_cache("123", "public", "999")

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

    def test_query_remote_buildid_handles_missing_timeout_and_fallbacks(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            missing = Path(tmp) / "missing-steamcmd.exe"
            steamcmd = Path(tmp) / "steamcmd.exe"
            steamcmd.write_text("", encoding="utf-8")

            self.assertIsNone(steam_version._query_remote_buildid(missing, "123", "public", 5))

            with mock.patch.object(
                steam_version.subprocess,
                "run",
                side_effect=steam_version.subprocess.TimeoutExpired(cmd="steamcmd", timeout=1),
            ):
                self.assertIsNone(steam_version._query_remote_buildid(steamcmd, "123", "public", 1))

            with mock.patch.object(steam_version.subprocess, "run", side_effect=OSError("failed")):
                self.assertIsNone(steam_version._query_remote_buildid(steamcmd, "123", "public", 1))

            public_output = '''
            "branches"
            {
                "public"
                {
                    "buildid" "111"
                }
            }
            '''
            with mock.patch.object(
                steam_version.subprocess,
                "run",
                return_value=mock.Mock(stdout=public_output),
            ) as run:
                self.assertEqual(steam_version._query_remote_buildid(steamcmd, "123", "beta", 5), "111")
            self.assertEqual(run.call_count, 2)

            any_output = '"depots" { "buildid" "333" }'
            with mock.patch.object(
                steam_version.subprocess,
                "run",
                return_value=mock.Mock(stdout=any_output),
            ):
                self.assertEqual(steam_version._query_remote_buildid(steamcmd, "123", "public", 5), "333")

            no_build_output = '"branches" { "public" { "description" "none" } }'
            with mock.patch.object(
                steam_version.subprocess,
                "run",
                return_value=mock.Mock(stdout=no_build_output),
            ):
                self.assertIsNone(steam_version._query_remote_buildid(steamcmd, "123", "public", 5))

    def test_get_versions_uses_installed_cache_and_remote_fallbacks(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            server_dir = base / "Server"
            manifest = server_dir / "steamapps" / "appmanifest_123.acf"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('"buildid" "456"\n', encoding="utf-8")
            steamcmd = base / "steamcmd.exe"
            steamcmd.write_text("", encoding="utf-8")

            cfg = {
                "server_dir": str(server_dir),
                "steamcmd_path": str(steamcmd),
                "app_id": "123",
                "steam_update_beta": "beta",
            }
            with mock.patch.dict(steam_version.config, cfg, clear=True), mock.patch.object(
                steam_version,
                "get_path",
                side_effect=lambda key: cfg.get(key, ""),
            ), mock.patch.object(
                steam_version,
                "_load_cache",
                return_value={"buildid": "999", "fetched_at": int(time.time())},
            ), mock.patch.object(
                steam_version,
                "_cache_fresh",
                return_value=True,
            ), mock.patch.object(
                steam_version,
                "_query_remote_buildid",
            ) as query:
                result = steam_version.get_versions()

            self.assertTrue(result["ok"])
            self.assertEqual(result["installed_buildid"], "456")
            self.assertEqual(result["remote_buildid"], "999")
            self.assertEqual(result["branch"], "beta")
            self.assertTrue(result["cached"])
            query.assert_not_called()

            with mock.patch.dict(steam_version.config, cfg, clear=True), mock.patch.object(
                steam_version,
                "get_path",
                side_effect=lambda key: cfg.get(key, ""),
            ), mock.patch.object(
                steam_version,
                "_load_cache",
                return_value={"buildid": "old"},
            ), mock.patch.object(
                steam_version,
                "_cache_fresh",
                return_value=False,
            ), mock.patch.object(
                steam_version,
                "_query_remote_buildid",
                return_value="1000",
            ) as query, mock.patch.object(
                steam_version,
                "_save_cache",
            ) as save:
                result = steam_version.get_versions(branch="public", use_cache=True)

            self.assertEqual(result["remote_buildid"], "1000")
            self.assertFalse(result["cached"])
            query.assert_called_once()
            save.assert_called_once_with("123", "public", "1000")

    def test_get_versions_returns_empty_result_without_app_id(self) -> None:
        cfg = {"server_dir": str(ROOT), "app_id": ""}
        with mock.patch.dict(steam_version.config, cfg, clear=True), mock.patch.object(
            steam_version,
            "get_path",
            side_effect=lambda key: cfg.get(key, ""),
        ):
            result = steam_version.get_versions()

        self.assertFalse(result["ok"])
        self.assertEqual(result["app_id"], "")

    def test_invalidate_cache_removes_existing_cache_and_ignores_errors(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cache = Path(tmp) / "cache.json"
            cache.write_text("{}", encoding="utf-8")
            with mock.patch.object(steam_version, "_cache_path", return_value=cache):
                steam_version.invalidate_cache("123", "public")
            self.assertFalse(cache.exists())

            with mock.patch.object(steam_version, "_cache_path", side_effect=OSError("bad")):
                steam_version.invalidate_cache("123", "public")

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

        defaults = steam_version._parse_args(["--timeout", "bad", "--ttl", "bad"])
        self.assertEqual(defaults["timeout"], 15)
        self.assertEqual(defaults["ttl"], 300)

    def test_main_prints_status_json_plain_and_returns_data_based_code(self) -> None:
        payload = {
            "status": "Up-to-date",
            "color": "green",
            "branch": "public",
            "installed_buildid": "1",
            "remote_buildid": "1",
            "cached": True,
        }
        with mock.patch.object(steam_version, "get_version_status", return_value=payload), mock.patch(
            "builtins.print"
        ) as printed:
            self.assertEqual(steam_version.main(["--status"]), 0)
        self.assertGreaterEqual(printed.call_count, 5)

        with mock.patch.object(steam_version, "get_version_status", return_value=payload), mock.patch(
            "builtins.print"
        ) as printed:
            self.assertEqual(steam_version.main(["--status", "--json"]), 0)
        self.assertEqual(json.loads(printed.call_args.args[0])["status"], "Up-to-date")

        empty = {**payload, "installed_buildid": None, "remote_buildid": None}
        with mock.patch.object(steam_version, "get_version_status", return_value=empty), mock.patch(
            "builtins.print"
        ):
            self.assertEqual(steam_version.main(["--status"]), 1)

    def test_main_prints_version_json_plain_and_up_to_date_line(self) -> None:
        payload = {
            "branch": "public",
            "installed_buildid": "1",
            "remote_buildid": "2",
            "cached": False,
        }
        with mock.patch.object(steam_version, "get_versions", return_value=payload), mock.patch(
            "builtins.print"
        ) as printed:
            self.assertEqual(steam_version.main([]), 0)
        self.assertTrue(any("Up-to-date" in call.args[0] for call in printed.call_args_list))

        with mock.patch.object(steam_version, "get_versions", return_value=payload), mock.patch(
            "builtins.print"
        ) as printed:
            self.assertEqual(steam_version.main(["--json", "--no-cache"]), 0)
        self.assertEqual(json.loads(printed.call_args.args[0])["remote_buildid"], "2")

        empty = {**payload, "installed_buildid": None, "remote_buildid": None}
        with mock.patch.object(steam_version, "get_versions", return_value=empty), mock.patch(
            "builtins.print"
        ):
            self.assertEqual(steam_version.main([]), 1)


if __name__ == "__main__":
    unittest.main()
