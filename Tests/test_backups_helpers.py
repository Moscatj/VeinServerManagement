from __future__ import annotations

import hashlib
import sys
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
    def test_cfg_to_dict_handles_dict_dataclass_like_attrs(self) -> None:
        class Obj:
            backups = {"root": "Backups"}
            runtime_dir = "Runtime"
            ignored = "ignored"

        self.assertEqual(backups._cfg_to_dict({"a": 1}), {"a": 1})
        self.assertEqual(backups._cfg_to_dict(Obj())["backups"], {"root": "Backups"})
        self.assertEqual(backups._cfg_to_dict(Obj())["runtime_dir"], "Runtime")

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
                self.assertEqual(backups._retention_for("Manual"), {"max_backups": 5, "max_age_days": 3})
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


if __name__ == "__main__":
    unittest.main()
