from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Controller.Tools import documentation_check  # noqa: E402


class DocumentationCheckTests(unittest.TestCase):
    def _repo(self, root: Path, version: str = "2.9.0") -> None:
        (root / "Docs").mkdir(parents=True)
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n"
            "## Unreleased\n\n"
            f"## {version} - 2026-07-13\n\n"
            "- Current release notes.\n\n"
            "## 2.8.0 - 2026-07-11\n\n"
            "- Previous release notes.\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            f"The current stable release is **v{version}**.\n"
            "Example: `VeinServerManagement-Setup-vX.Y.Z.exe`.\n",
            encoding="utf-8",
        )
        (root / "ROADMAP.md").write_text(
            f"Released through `v{version}`:\n", encoding="utf-8"
        )
        (root / "RELEASING.md").write_text(
            f"The current release baseline is `v{version}`.\n", encoding="utf-8"
        )
        (root / "Docs" / "_index.md").write_text(
            f"> **Version baseline:** v{version}\n", encoding="utf-8"
        )
        (root / "Docs" / "docs_for_codex.md").write_text(
            f"The current stable baseline is v{version}.\n", encoding="utf-8"
        )

    def test_consistent_repository_and_matching_tag_pass(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)

            self.assertEqual(
                documentation_check.check_documentation(root, tag="v2.9.0"), []
            )

    def test_declaration_conflict_reports_file_and_expected_version(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "README.md").write_text(
                "The current stable release is **v2.8.0**.\n",
                encoding="utf-8",
            )

            errors = documentation_check.check_documentation(root)

            self.assertTrue(any("README.md" in error for error in errors))
            self.assertTrue(any("expects v2.9.0" in error for error in errors))

    def test_release_tag_must_match_changelog(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)

            errors = documentation_check.check_documentation(root, tag="v2.9.1")

            self.assertTrue(any("does not match" in error for error in errors))

    def test_release_tag_must_use_semver_format(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)

            errors = documentation_check.check_documentation(root, tag="release-2.9")

            self.assertTrue(any("invalid" in error for error in errors))

    def test_hardcoded_installer_example_is_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Docs" / "packaging.md").write_text(
                "Download `VeinServerManagement-Setup-v2.9.0.exe`.\n",
                encoding="utf-8",
            )

            errors = documentation_check.check_documentation(root)

            self.assertTrue(any("use VeinServerManagement-Setup-vX.Y.Z.exe" in error for error in errors))

    def test_changelog_versions_must_descend(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            changelog = changelog.replace(
                "## 2.8.0 - 2026-07-11", "## 3.0.0 - 2026-07-11"
            )
            (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

            errors = documentation_check.check_documentation(root)

            self.assertTrue(any("descending version order" in error for error in errors))

    def test_current_changelog_release_requires_notes(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            changelog = changelog.replace("- Current release notes.\n", "")
            (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")

            errors = documentation_check.check_documentation(root)

            self.assertTrue(any("has no bullet release notes" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
