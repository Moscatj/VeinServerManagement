from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.backup_policy import (  # noqa: E402
    BackupPolicy,
    apply_backup_policy,
    backup_policy_from_mapping,
    backup_policy_summary,
    load_backup_policy,
    validate_backup_policy,
)


class BackupPolicyTests(unittest.TestCase):
    def test_policy_reads_supported_triggers_and_retention(self) -> None:
        policy = backup_policy_from_mapping(
            {
                "backups": {
                    "enabled": False,
                    "recovery": {"restore_missing_on_start": False},
                    "triggers": {
                        "on_autosave": True,
                        "on_crash_detect": {"enabled": False},
                        "shutdown": {"save_backup": True},
                    },
                    "retention": {
                        "default": {
                            "enabled": True,
                            "by_count": False,
                            "by_age": True,
                            "minimum_backups": 4,
                            "max_backups": 25,
                            "max_age_days": 14,
                        }
                    },
                }
            }
        )

        self.assertFalse(policy.enabled)
        self.assertFalse(policy.startup_recovery_enabled)
        self.assertTrue(policy.on_autosave)
        self.assertFalse(policy.on_crash_detect)
        self.assertTrue(policy.on_shutdown)
        self.assertTrue(policy.cleanup_enabled)
        self.assertFalse(policy.cleanup_by_count)
        self.assertTrue(policy.cleanup_by_age)
        self.assertEqual(policy.minimum_backups, 4)
        self.assertEqual(policy.max_backups, 25)
        self.assertEqual(policy.max_age_days, 14)

    def test_policy_validation_and_summary_are_operator_facing(self) -> None:
        policy = BackupPolicy(on_autosave=True, max_backups=20, max_age_days=30)

        validate_backup_policy(policy)
        summary = backup_policy_summary(policy)

        self.assertIn("Autosave", summary)
        self.assertIn("maximum 20 archive(s) per type", summary)
        self.assertIn("maximum age 30 day(s)", summary)
        self.assertIn("always keep at least 3", summary)
        with self.assertRaisesRegex(ValueError, "Minimum retained"):
            validate_backup_policy(BackupPolicy(minimum_backups=0))
        with self.assertRaisesRegex(ValueError, "cannot be lower"):
            validate_backup_policy(BackupPolicy(minimum_backups=5, max_backups=4))
        with self.assertRaisesRegex(ValueError, "count retention"):
            validate_backup_policy(BackupPolicy(max_backups=0))
        with self.assertRaisesRegex(ValueError, "age retention"):
            validate_backup_policy(BackupPolicy(max_age_days=0))
        with self.assertRaisesRegex(ValueError, "requires the primary YAML"):
            load_backup_policy("Config/config.json")

    def test_legacy_small_count_derives_compatible_safety_floor(self) -> None:
        policy = backup_policy_from_mapping(
            {"backups": {"retention": {"default": {"max_backups": 1}}}}
        )

        self.assertEqual(policy.minimum_backups, 1)
        validate_backup_policy(policy)

    def test_apply_policy_backs_up_writes_atomically_and_post_validates(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            config_dir = base / "Config"
            config_dir.mkdir()
            config_path = config_dir / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "version": "2.4",
                        "backups": {
                            "enabled": True,
                            "root": "Backups",
                            "max_backups": 9,
                            "backup_max_age_days": 6,
                            "triggers": {"on_autosave": False},
                        },
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            policy = BackupPolicy(
                enabled=False,
                startup_recovery_enabled=False,
                on_autosave=True,
                on_crash_detect=False,
                on_shutdown=False,
                cleanup_enabled=True,
                cleanup_by_count=False,
                cleanup_by_age=True,
                minimum_backups=5,
                max_backups=40,
                max_age_days=60,
            )

            result = apply_backup_policy(config_path, policy)
            loaded = load_backup_policy(config_path)
            saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))

            self.assertTrue(result.changed)
            self.assertTrue(Path(result.backup).is_file())
            self.assertEqual(loaded, policy)
            self.assertFalse(saved["backups"]["triggers"]["shutdown"]["save_backup"])
            self.assertFalse(
                saved["backups"]["recovery"]["restore_missing_on_start"]
            )
            self.assertEqual(
                saved["backups"]["retention"]["default"]["max_backups"], 40
            )
            self.assertFalse(
                saved["backups"]["retention"]["default"]["by_count"]
            )
            self.assertNotIn("max_backups", saved["backups"])
            self.assertNotIn("backup_max_age_days", saved["backups"])
            self.assertTrue(saved["backups"]["retention"]["default"]["by_age"])
            self.assertEqual(
                saved["backups"]["retention"]["default"]["minimum_backups"], 5
            )
            self.assertFalse(config_path.with_suffix(".yaml.tmp").exists())

            noop = apply_backup_policy(config_path, policy)
            self.assertFalse(noop.changed)
            self.assertEqual(noop.backup, "")


if __name__ == "__main__":
    unittest.main()
