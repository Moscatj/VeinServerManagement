from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import backups_api  # noqa: E402


class BackupsApiTests(unittest.TestCase):
    def test_make_backup_delegates_to_backups_module(self) -> None:
        with mock.patch.object(backups_api._backups, "make_backup", return_value=Path("out.zip")) as make:
            result = backups_api.make_backup(save_path=Path("ignored.sav"), reason="Manual", dst=Path("dst"))

        self.assertEqual(result, Path("out.zip"))
        make.assert_called_once_with(reason="Manual", files=None, dst=Path("dst"))

    def test_prune_and_restore_delegate(self) -> None:
        with mock.patch.object(backups_api._backups, "prune_backups") as prune, mock.patch.object(
            backups_api._backups,
            "restore_from_latest",
            return_value=True,
        ) as restore:
            backups_api.prune_backups(Path("Backups"))
            restored = backups_api.restore_from_latest("Server.vns")

        prune.assert_called_once_with(path=Path("Backups"))
        restore.assert_called_once_with("Server.vns")
        self.assertTrue(restored)


if __name__ == "__main__":
    unittest.main()
