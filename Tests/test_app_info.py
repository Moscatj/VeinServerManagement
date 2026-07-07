from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import app_info  # noqa: E402


class AppInfoTests(unittest.TestCase):
    def test_version_prefers_environment_and_strips_v_prefix(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            with mock.patch.dict(os.environ, {"VEIN_APP_VERSION": "v9.8.7"}):
                self.assertEqual(app_info.get_app_version(Path(tmp)), "9.8.7")

    def test_version_reads_packaged_version_file(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            (root / app_info.VERSION_FILE).write_text("2.3.14\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(app_info.get_app_version(root), "2.3.14")

    def test_about_info_contains_release_metadata(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            (root / app_info.VERSION_FILE).write_text("2.3.14\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {}, clear=True):
                info = app_info.build_about_info(
                    root,
                    config_path=root / "Config" / "config.yaml",
                    frozen=True,
                )

        self.assertEqual(info["version"], "2.3.14")
        self.assertEqual(info["commit"], "unknown")
        self.assertEqual(info["mode"], "Packaged")
        self.assertIn("config.yaml", info["config"])

    def test_about_info_default_does_not_call_git(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            with mock.patch.object(app_info, "_git_value", side_effect=AssertionError("git should not run")):
                info = app_info.build_about_info(Path(tmp))

        self.assertEqual(info["version"], app_info.UNKNOWN_VERSION)
        self.assertEqual(info["commit"], "unknown")

    def test_about_info_can_include_git_when_requested(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            def fake_git(_root: Path, *args: str) -> str:
                if args and args[0] == "describe":
                    return "v2.4.0"
                return "abc1234"

            with mock.patch.object(app_info, "_git_value", side_effect=fake_git):
                info = app_info.build_about_info(Path(tmp), include_git=True)

        self.assertEqual(info["version"], "v2.4.0")
        self.assertEqual(info["commit"], "abc1234")


if __name__ == "__main__":
    unittest.main()
