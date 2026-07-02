from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-installer.yml"
BUILD_INSTALLER = ROOT / "Scripts" / "BuildInstaller.bat"


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_installer_workflow_builds_only_for_tags_or_manual_dispatch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", text)
        self.assertIn('"v*.*.*"', text)
        self.assertIn("if: startsWith(github.ref, 'refs/tags/')", text)

    def test_release_installer_workflow_uses_node24_compatible_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("uses: actions/checkout@v7", text)
        self.assertIn("uses: actions/setup-python@v6", text)
        self.assertIn("uses: actions/upload-artifact@v6", text)
        self.assertIn("uses: softprops/action-gh-release@v3", text)

    def test_build_installer_batch_does_not_pause_in_ci(self) -> None:
        text = BUILD_INSTALLER.read_text(encoding="utf-8")

        self.assertIn('if /i not "%CI%"=="true" pause', text)

    def test_release_installer_workflow_uses_setup_python_path(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("PYTHON_BIN: python", text)
        self.assertIn(
            "python -m pip install -r requirements-dev.txt -r requirements-packaging.txt",
            text,
        )


if __name__ == "__main__":
    unittest.main()
