from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
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

from Tools import backups  # noqa: E402


class BackupsHelperTests(unittest.TestCase):
    def test_list_backup_archives_returns_newest_with_category_and_size(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            manual = root / "Manual"
            manual.mkdir()
            older = root / "loose.zip"
            newer = manual / "newer.zip"
            older.write_bytes(b"old")
            newer.write_bytes(b"newer")
            older.touch()
            newer.touch()
            now = time.time()
            os.utime(older, (now - 20, now - 20))
            os.utime(newer, (now - 10, now - 10))

            archives = backups.list_backup_archives(root)

        self.assertEqual([item.filename for item in archives], ["newer.zip", "loose.zip"])
        self.assertEqual(archives[0].category, "Manual")
        self.assertEqual(archives[1].category, "Root")
        self.assertEqual(archives[0].size_bytes, 5)

    def test_list_backup_archives_handles_missing_root_and_limit(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            for index in range(3):
                (root / f"backup-{index}.zip").write_bytes(str(index).encode())

            archives = backups.list_backup_archives(root, limit=2)
            all_archives = backups.list_backup_archives(root, limit=None)
            missing = backups.list_backup_archives(root / "missing")

        self.assertEqual(len(archives), 2)
        self.assertEqual(len(all_archives), 3)
        self.assertEqual(missing, [])

    def test_cfg_to_dict_handles_dict_dataclass_like_attrs(self) -> None:
        class Obj:
            backups = {"root": "Backups"}
            runtime_dir = "Runtime"
            ignored = "ignored"

        self.assertEqual(backups._cfg_to_dict({"a": 1}), {"a": 1})
        self.assertEqual(backups._cfg_to_dict(Obj())["backups"], {"root": "Backups"})
        self.assertEqual(backups._cfg_to_dict(Obj())["runtime_dir"], "Runtime")

    def test_cfg_to_dict_handles_adapter_methods_and_dataclasses(self) -> None:
        class ToDictObj:
            def to_dict(self) -> dict:
                return {"backups": {"root": "A"}}

        class AsDictObj:
            def as_dict(self) -> dict:
                return {"runtime_dir": "RuntimeA"}

        @dataclass
        class DataConfig:
            backups: dict
            runtime_dir: str

        self.assertEqual(backups._cfg_to_dict(ToDictObj()), {"backups": {"root": "A"}})
        self.assertEqual(backups._cfg_to_dict(AsDictObj()), {"runtime_dir": "RuntimeA"})
        self.assertEqual(
            backups._cfg_to_dict(DataConfig(backups={"root": "B"}, runtime_dir="RuntimeB")),
            {"backups": {"root": "B"}, "runtime_dir": "RuntimeB"},
        )

    def test_backup_path_helpers_use_config_view(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = {
                "backups": {
                    "root": str(base / "Backups"),
                    "folders": {"Manual": "ManualFolder"},
                    "retention": {
                        "default": {"max_backups": 2, "max_age_days": 3},
                        "Manual": {"max_backups": 5},
                    },
                    "save_dir": str(base / "Saved"),
                    "save_filenames": ["A.sav", "B.sav"],
                    "discord": {"notify_on_create": False, "notify_on_prune": True},
                },
                "features": {"enable_backups": True},
            }

            with mock.patch.object(backups, "_cfg", return_value=cfg):
                self.assertEqual(backups._root(), base / "Backups")
                self.assertEqual(backups._dest_for("Manual"), base / "Backups" / "ManualFolder")
                self.assertEqual(
                    backups._retention_for("Manual"),
                    {
                        "enabled": True,
                        "by_count": True,
                        "by_age": True,
                        "minimum_backups": 3,
                        "max_backups": 5,
                        "max_age_days": 3,
                    },
                )
                self.assertEqual(backups._save_candidates(), [base / "Saved" / "A.sav", base / "Saved" / "B.sav"])
                self.assertEqual(backups._discord_flags(), {"on_create": False, "on_prune": True})

    def test_pick_existing_save_and_sha256(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            save = Path(tmp) / "Server.vns"
            save.write_bytes(b"hello")
            with mock.patch.object(backups, "_save_candidates", return_value=[Path(tmp) / "missing.vns", save]):
                chosen = backups._pick_existing_save()

            digest = backups._sha256(save)

        self.assertEqual(chosen, save)
        self.assertEqual(digest, hashlib.sha256(b"hello").hexdigest())

    def test_pick_existing_save_reports_missing_candidates_and_discord(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            candidates = [Path(tmp) / "missing-a.vns", Path(tmp) / "missing-b.vns"]
            with mock.patch.object(backups, "_save_candidates", return_value=candidates), mock.patch.object(
                backups,
                "is_discord_channel_enabled",
                return_value=True,
            ), mock.patch.object(backups, "send_discord_message") as discord, mock.patch(
                "builtins.print"
            ) as printed:
                self.assertIsNone(backups._pick_existing_save())

        printed.assert_called_once()
        discord.assert_called_once()

    def test_runtime_dir_and_state_writer_tolerate_config_and_write_failures(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            cfg = {
                "runtime_dir": str(base / "Runtime"),
                "backups": {
                    "root": str(base / "Backups"),
                    "folders": {"Manual": "Manual"},
                },
            }
            (base / "Backups" / "Manual").mkdir(parents=True)
            (base / "Backups" / "Manual" / "one.zip").write_text("zip", encoding="utf-8")
            with mock.patch.object(backups, "_cfg", return_value=cfg):
                self.assertEqual(backups._runtime_dir(), base / "Runtime")
                counts = backups._count_all()

            with mock.patch.object(backups, "_cfg", side_effect=RuntimeError("bad config")):
                self.assertEqual(backups._runtime_dir().name, "Runtime")

            with mock.patch.object(backups, "_runtime_dir", return_value=base / "Runtime"), mock.patch.object(
                backups,
                "_root",
                return_value=base / "Backups",
            ), mock.patch.object(
                backups,
                "_count_all",
                return_value={"TOTAL": 1},
            ), mock.patch.object(
                backups,
                "write_state",
                side_effect=OSError("cannot write"),
            ), mock.patch(
                "builtins.print"
            ) as printed:
                backups._write_backup_state(last_reason="Manual", last_zip=base / "Backups" / "one.zip")

        self.assertEqual(counts["Manual"], 1)
        self.assertEqual(counts["TOTAL"], 1)
        printed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
