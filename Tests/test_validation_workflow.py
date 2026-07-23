from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_PS1 = ROOT / "Scripts" / "ValidateChange.ps1"
VALIDATE_BAT = ROOT / "Scripts" / "ValidateChange.bat"
PUBLISH_PS1 = ROOT / "Scripts" / "PublishValidated.ps1"
PUBLISH_BAT = ROOT / "Scripts" / "PublishValidated.bat"
TEST_SUITE_BAT = ROOT / "Scripts" / "TestSuite.bat"
COVERAGE_BAT = ROOT / "Scripts" / "RunCoverage.bat"


class ValidationWorkflowTests(unittest.TestCase):
    def test_validation_wrapper_uses_process_scoped_policy_bypass(self) -> None:
        text = VALIDATE_BAT.read_text(encoding="utf-8")

        self.assertIn("-ExecutionPolicy Bypass", text)
        self.assertIn("ValidateChange.ps1", text)

    def test_validation_engine_contains_required_gates(self) -> None:
        text = VALIDATE_PS1.read_text(encoding="utf-8")

        for expected in (
            "VEIN_DISABLE_DISCORD",
            "documentation_check.py",
            "source_hygiene_check.py",
            "architecture_check.py",
            "unittest discover -s Tests",
            "Controller\\health_check.py",
            "TestSuite.bat",
            "RunCoverage.bat",
            "git diff --check",
            "git diff --cached --check",
        ):
            self.assertIn(expected, text)

    def test_all_local_test_runners_disable_discord(self) -> None:
        for path in (VALIDATE_PS1, TEST_SUITE_BAT, COVERAGE_BAT):
            with self.subTest(path=path.name):
                self.assertIn("VEIN_DISABLE_DISCORD", path.read_text(encoding="utf-8"))

    def test_publish_validates_before_commit_and_push_then_watches_ci(self) -> None:
        text = PUBLISH_PS1.read_text(encoding="utf-8")

        validate = text.index("ValidateChange.ps1")
        commit = text.index("git commit")
        push = text.index("git push")
        watch = text.index("gh run watch")
        self.assertLess(validate, commit)
        self.assertLess(commit, push)
        self.assertLess(push, watch)
        self.assertIn("--commit $commit --workflow ci.yml", text)
        self.assertIn("$parsedRuns.Count -gt 0", text)
        self.assertNotIn("git add", text)

    def test_publish_supports_clean_fast_forward_existing_commit_chains(self) -> None:
        text = PUBLISH_PS1.read_text(encoding="utf-8")

        self.assertIn("[switch]$ExistingCommits", text)
        self.assertIn('git merge-base --is-ancestor "$Remote/$Branch" HEAD', text)
        self.assertIn('git rev-list --count "$Remote/$Branch..HEAD"', text)
        self.assertIn('$commit = $localHead', text)
        self.assertIn('git push $Remote "HEAD:$Branch"', text)
        self.assertIn("existing commit messages are preserved", text)

    def test_publish_wrapper_uses_process_scoped_policy_bypass(self) -> None:
        text = PUBLISH_BAT.read_text(encoding="utf-8")

        self.assertIn("-ExecutionPolicy Bypass", text)
        self.assertIn("PublishValidated.ps1", text)


if __name__ == "__main__":
    unittest.main()
