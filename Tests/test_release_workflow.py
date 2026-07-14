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
        self.assertIn('findstr /c:"Python 3.13"', text)

    def test_release_installer_workflow_uses_setup_python_path(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("PYTHON_BIN: python", text)
        self.assertIn(
            "python -m pip install -r requirements-dev.txt -r requirements-packaging.txt",
            text,
        )

    def test_release_installer_workflow_uploads_versioned_installer_name(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        build_script = BUILD_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("name: VeinServerManagement-Setup-${{ github.ref_name }}", workflow)
        self.assertIn("path: dist/installer/VeinServerManagement-Setup-v*.exe", workflow)
        self.assertIn("files: dist/installer/VeinServerManagement-Setup-v*.exe", workflow)
        self.assertIn(
            "VeinServerManagement-Setup-v%PACKAGE_VERSION%.exe",
            build_script,
        )

    def test_release_installer_workflow_publishes_changelog_notes(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Extract release notes from changelog", workflow)
        self.assertIn("CHANGELOG.md does not contain release notes", workflow)
        self.assertIn("Set-Content -Path release-notes.md", workflow)
        self.assertIn("body_path: release-notes.md", workflow)

    def test_release_installer_workflow_checks_tag_and_documentation_before_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        check = workflow.index("Check documentation, changelog, and release version")
        install = workflow.index("Install Python app and packaging dependencies")
        build = workflow.index("Build installer")
        self.assertLess(check, install)
        self.assertLess(check, build)
        self.assertIn("documentation_check.py --tag", workflow)
        self.assertIn("github.ref_name", workflow)

    def test_normal_ci_checks_documentation_version_consistency(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("Run repository validation", workflow)
        self.assertIn("Scripts\\ValidateChange.bat -PythonExe python", workflow)
        self.assertIn("python -m pip install -r requirements-dev.txt", workflow)
        self.assertNotIn("py -3 -m pip install -r requirements-dev.txt", workflow)

        validation = (ROOT / "Scripts" / "ValidateChange.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("documentation_check.py", validation)
        self.assertIn("source_hygiene_check.py", validation)
        self.assertIn("TestSuite.bat", validation)
        self.assertIn("RunCoverage.bat", validation)


if __name__ == "__main__":
    unittest.main()
