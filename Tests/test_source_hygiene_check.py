from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Controller.Tools import source_hygiene_check  # noqa: E402


class SourceHygieneCheckTests(unittest.TestCase):
    def test_clean_text_passes(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            path = root / "README.md"
            path.write_text("Sanitized project documentation.\n", encoding="utf-8")

            self.assertEqual(source_hygiene_check.scan_paths(root, [path]), [])

    def test_secret_pattern_is_reported(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            path = root / "unsafe.txt"
            token = "ghp_" + ("a" * 24)
            path.write_text(f"token={token}\n", encoding="utf-8")

            findings = source_hygiene_check.scan_paths(root, [path])

            self.assertEqual(len(findings), 1)
            self.assertIn("unsafe.txt", findings[0])

    def test_external_path_is_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            findings = source_hygiene_check.scan_paths(root, [ROOT / "README.md"])

            self.assertTrue(any("outside the repository" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
