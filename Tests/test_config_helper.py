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

import config_helper  # noqa: E402


class ConfigHelperTests(unittest.TestCase):
    def test_feature_and_discord_channel_flags(self) -> None:
        with mock.patch.dict(
            config_helper.features,
            {"enable_discord": True, "discord_startup": False, "custom": True},
            clear=True,
        ):
            self.assertTrue(config_helper.is_feature_enabled("custom"))
            self.assertFalse(config_helper.is_discord_channel_enabled("startup"))
            self.assertTrue(config_helper.is_discord_channel_enabled("crash"))

        with mock.patch.dict(config_helper.features, {"enable_discord": False}, clear=True):
            self.assertFalse(config_helper.is_discord_channel_enabled("crash"))

    def test_typed_getters_handle_bad_values_and_defaults(self) -> None:
        with mock.patch.dict(
            config_helper.config,
            {"truthy": 1, "bad_int": "x", "items": [1, 2], "mapping": {"a": 1}, "path": "."},
            clear=True,
        ):
            self.assertTrue(config_helper.get_bool("truthy"))
            self.assertEqual(config_helper.get_int("bad_int", 7), 7)
            self.assertEqual(config_helper.get_list("items"), [1, 2])
            self.assertEqual(config_helper.get_list("missing", ["a"]), ["a"])
            self.assertEqual(config_helper.get_dict("mapping"), {"a": 1})
            self.assertEqual(config_helper.get_dict("missing", {"b": 2}), {"b": 2})
            self.assertTrue(Path(config_helper.get_path("path")).is_absolute())

    def test_backups_helpers_normalize_view(self) -> None:
        with mock.patch.dict(
            config_helper.config,
            {
                "backups": {
                    "enabled": False,
                    "root": "Backups",
                    "folders": {"Manual": "Manual"},
                    "save_dir": "Saved",
                    "triggers": {
                        "on_autosave": False,
                        "on_crash_detect": {"enabled": True},
                        "shutdown": {"save_backup": False},
                    },
                    "retention": {
                        "default": {"max_backups": "3", "max_age_days": "4"},
                        "Manual": {"max_backups": "5", "max_age_days": "6"},
                    },
                }
            },
            clear=True,
        ):
            view = config_helper.backups_cfg()
            self.assertFalse(config_helper.backups_enabled())
            self.assertFalse(config_helper.backup_trigger_enabled("on_autosave"))
            self.assertTrue(config_helper.backup_trigger_enabled("on_crash_detect"))
            self.assertFalse(config_helper.backup_trigger_enabled("shutdown"))
            self.assertTrue(config_helper.backup_trigger_enabled("unknown"))
            self.assertTrue(Path(view["root"]).is_absolute())
            self.assertEqual(config_helper.backup_folders(), {"Manual": str(Path("Manual").resolve())})
            self.assertEqual(
                config_helper.backup_retention_for("Manual"),
                {
                    "enabled": True,
                    "by_count": True,
                    "by_age": True,
                    "minimum_backups": 3,
                    "max_backups": 5,
                    "max_age_days": 6,
                },
            )
            self.assertEqual(
                config_helper.backup_retention_for("Other"),
                {
                    "enabled": True,
                    "by_count": True,
                    "by_age": True,
                    "minimum_backups": 3,
                    "max_backups": 3,
                    "max_age_days": 4,
                },
            )

    def test_path_helpers_use_structured_and_legacy_fallbacks(self) -> None:
        with mock.patch.dict(
            config_helper.config,
            {
                "paths": {
                    "logs": "Logs",
                    "saves_dir": "Saved",
                    "backup_root": "Backups",
                }
            },
            clear=True,
        ):
            paths = config_helper.paths_cfg()

            self.assertTrue(Path(paths["logs"]).is_absolute())
            self.assertEqual(config_helper.logs_dir(), str(Path("Logs").resolve()))
            self.assertEqual(config_helper.saves_dir(), str(Path("Saved").resolve()))
            self.assertEqual(config_helper.backup_root(), str(Path("Backups").resolve()))

        with mock.patch.dict(
            config_helper.config,
            {"logs_dir": "LegacyLogs", "save_dir": "LegacySaves"},
            clear=True,
        ):
            self.assertEqual(config_helper.logs_dir(), str(Path("LegacyLogs").resolve()))
            self.assertEqual(config_helper.saves_dir(), str(Path("LegacySaves").resolve()))

    def test_log_snapshot_defaults_and_overrides_are_normalized(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp) / "Backups"
            log_root = Path(tmp) / "LogCopies"
            with mock.patch.dict(
                config_helper.config,
                {
                    "backups": {
                        "root": str(root),
                        "logs": {
                            "root": str(log_root),
                            "max_files": 12,
                            "tail_kb": 64,
                        },
                    }
                },
                clear=True,
            ):
                logs = config_helper.log_snap_cfg()

        self.assertTrue(logs["enabled"])
        self.assertEqual(logs["root"], str(log_root.resolve()))
        self.assertEqual(logs["max_files"], 12)
        self.assertEqual(logs["max_age_days"], 30)
        self.assertEqual(logs["tail_kb"], 64)
        self.assertFalse(logs["include_tail_in_saves"])

    def test_migrate_backups_view_builds_legacy_view_in_memory(self) -> None:
        payload = {
            "backup_root": "LegacyBackups",
            "backup_folders": {"Manual": "Manual"},
            "save_filenames": ["world.sav"],
            "save_dir": "Saved",
            "max_backups": "4",
            "backup_max_age_days": "8",
            "nightly_backup": {"max_backups": "9", "max_backup_age_days": "31"},
        }
        with mock.patch.dict(config_helper.config, payload, clear=True), mock.patch.dict(
            config_helper.features,
            {"enable_backups": False},
            clear=True,
        ):
            config_helper._migrate_backups_view()
            backups = config_helper.config["backups"]

            self.assertIs(backups, config_helper.config["backup"])
            self.assertFalse(backups["enable"])
            self.assertFalse(backups["enabled"])
            self.assertEqual(backups["root"], "LegacyBackups")
            self.assertEqual(backups["folders"], {"Manual": "Manual"})
            self.assertEqual(backups["save_filenames"], ["world.sav"])
            self.assertEqual(backups["save_dir"], "Saved")
            self.assertEqual(
                backups["retention"]["default"],
                {
                    "max_backups": 4,
                    "max_age_days": 8,
                    "enabled": True,
                    "by_count": True,
                    "by_age": True,
                    "minimum_backups": 3,
                },
            )
            self.assertEqual(
                backups["retention"]["Nightly"],
                {"max_backups": 9, "max_age_days": 31},
            )

    def test_deep_get_and_set_handle_missing_and_nested_paths(self) -> None:
        payload = {"a": {"b": 1}, "flat": 2}

        self.assertEqual(config_helper._deep_get(payload, "a.b"), 1)
        self.assertEqual(config_helper._deep_get(payload, "a.missing", "fallback"), "fallback")
        self.assertEqual(config_helper._deep_get(payload, "flat.value", 3), 3)

        config_helper._deep_set(payload, "a.c.d", 4)
        config_helper._deep_set(payload, "flat.value", 5)

        self.assertEqual(payload["a"]["c"]["d"], 4)
        self.assertEqual(payload["flat"]["value"], 5)


if __name__ == "__main__":
    unittest.main()
