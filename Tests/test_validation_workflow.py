from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_PS1 = ROOT / "Scripts" / "ValidateChange.ps1"
VALIDATE_BAT = ROOT / "Scripts" / "ValidateChange.bat"
PUBLISH_PS1 = ROOT / "Scripts" / "PublishValidated.ps1"
PUBLISH_BAT = ROOT / "Scripts" / "PublishValidated.bat"


class ValidationWorkflowTests(unittest.TestCase):
    def test_validation_wrapper_uses_process_scoped_policy_bypass(self) -> None:
        text = VALIDATE_BAT.read_text(encoding="utf-8")

        self.assertIn("-ExecutionPolicy Bypass", text)
        self.assertIn("ValidateChange.ps1", text)

    def test_validation_engine_contains_required_gates(self) -> None:
        text = VALIDATE_PS1.read_text(encoding="utf-8")

        for expected in (
            "documentation_check.py",
            "source_hygiene_check.py",
            "unittest discover -s Tests",
            "Controller\\health_check.py",
            "TestSuite.bat",
            "RunCoverage.bat",
            "git diff --check",
            "git diff --cached --check",
        ):
            self.assertIn(expected, text)

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
        self.assertNotIn("git add", text)

    def test_publish_wrapper_uses_process_scoped_policy_bypass(self) -> None:
        text = PUBLISH_BAT.read_text(encoding="utf-8")

        self.assertIn("-ExecutionPolicy Bypass", text)
        self.assertIn("PublishValidated.ps1", text)


if __name__ == "__main__":
    unittest.main()
