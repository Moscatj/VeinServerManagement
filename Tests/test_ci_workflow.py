from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_supported_python_versions_are_exercised(self) -> None:
        self.assertIn('python-version: ["3.11", "3.12"]', self.text)
        self.assertIn("Python ${{ matrix.python-version }} Unit Tests", self.text)
        self.assertIn("Full Repository Validation (Python 3.12)", self.text)

    def test_required_check_aggregates_all_jobs(self) -> None:
        self.assertIn("name: Unit Tests And Safety Checks", self.text)
        self.assertIn(
            "needs: [compatibility, validation, installer_smoke]", self.text
        )
        self.assertIn("Require every applicable CI job to pass", self.text)
        self.assertIn('${{ needs.compatibility.result }}', self.text)
        self.assertIn('${{ needs.validation.result }}', self.text)
        self.assertIn('${{ needs.installer_smoke.result }}', self.text)

    def test_installer_build_tracks_staged_bundle_inputs(self) -> None:
        for pattern in (
            "'^Controller/'",
            "'^Config/config\\.example\\.yaml$'",
            "'^Docs/'",
            "'^Installer/'",
            "'^Scripts/'",
            "'^Tests/fixtures/fake_vein_server\\.py$'",
            "'^requirements(?:-[^/]+)?\\.txt$'",
        ):
            self.assertIn(pattern, self.text)

    def test_installer_check_builds_and_uploads_temporary_artifact(self) -> None:
        self.assertIn("Install app and packaging dependencies", self.text)
        self.assertIn("choco install innosetup --no-progress --yes", self.text)
        self.assertIn("Scripts\\BuildInstaller.bat", self.text)
        self.assertIn("Upload temporary installer artifact", self.text)
        self.assertIn("uses: actions/upload-artifact@v6", self.text)
        self.assertIn("retention-days: 7", self.text)
        self.assertNotIn("softprops/action-gh-release", self.text)

    def test_installer_check_smoke_tests_packaged_install_and_uninstall(self) -> None:
        self.assertIn("Smoke test packaged install and uninstall", self.text)
        self.assertIn("Scripts\\SmokeTestInstaller.ps1", self.text)
        self.assertIn("Tests\\fixtures\\fake_vein_server.py", self.text)
        self.assertIn("-FakeServerPath", self.text)
        self.assertIn("timeout-minutes: 12", self.text)
        self.assertIn("Upload installer smoke diagnostics", self.text)
        self.assertIn("if: always() && steps.scope.outputs.relevant == 'true'", self.text)
        self.assertIn("dist/installer-smoke", self.text)

    def test_installer_steps_require_relevant_changes(self) -> None:
        self.assertGreaterEqual(
            self.text.count("if: steps.scope.outputs.relevant == 'true'"), 5
        )
        self.assertIn("if: steps.scope.outputs.relevant != 'true'", self.text)


if __name__ == "__main__":
    unittest.main()
