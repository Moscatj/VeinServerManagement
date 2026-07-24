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
from GUI import about  # noqa: E402


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
        self.assertEqual(
            info["release_notes"],
            "https://github.com/Moscatj/VeinServerManagement/releases/tag/v2.3.14",
        )
        self.assertIn("config.yaml", info["config"])

    def test_development_version_uses_latest_release_notes(self) -> None:
        self.assertEqual(
            app_info.release_notes_url("0.0.0-dev"),
            "https://github.com/Moscatj/VeinServerManagement/releases/latest",
        )

    def test_about_external_links_require_https(self) -> None:
        with mock.patch.object(
            about.QtGui.QDesktopServices,
            "openUrl",
            return_value=True,
        ) as open_url:
            self.assertFalse(about._open_https_url("file:///tmp/private"))
            self.assertFalse(about._open_https_url("javascript:alert(1)"))
            self.assertTrue(about._open_https_url("https://example.test/releases"))

        open_url.assert_called_once()
        self.assertEqual(
            open_url.call_args.args[0].toString(),
            "https://example.test/releases",
        )

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
