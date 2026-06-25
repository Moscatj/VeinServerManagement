from __future__ import annotations

import sys
import unittest
from pathlib import Path
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
            self.assertTrue(Path(view["root"]).is_absolute())
            self.assertEqual(config_helper.backup_folders(), {"Manual": str(Path("Manual").resolve())})
            self.assertEqual(
                config_helper.backup_retention_for("Manual"),
                {"max_backups": 5, "max_age_days": 6},
            )
            self.assertEqual(
                config_helper.backup_retention_for("Other"),
                {"max_backups": 3, "max_age_days": 4},
            )


if __name__ == "__main__":
    unittest.main()
