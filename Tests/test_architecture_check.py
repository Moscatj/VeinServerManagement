from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Controller.Tools import architecture_check  # noqa: E402


class ArchitectureCheckTests(unittest.TestCase):
    def _repo(self, root: Path) -> None:
        (root / "Controller" / "GUI").mkdir(parents=True)
        (root / "Tests").mkdir()
        (root / "Docs").mkdir()
        (root / "Controller" / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "Tests" / "test_feature.py").write_text("# test fixture\n", encoding="utf-8")
        (root / "Docs" / "feature.md").write_text("# Feature\n", encoding="utf-8")
        registry = {
            "version": 1,
            "coverage": {
                "source_roots": ["Controller"],
                "test_roots": ["Tests"],
                "exclude": ["Controller/Legacy", "Controller/**/__init__.py"],
            },
            "subsystems": {
                "feature": {
                    "risk": "medium",
                    "source": ["Controller/feature.py", "Controller/GUI"],
                    "tests": ["Tests/test_feature.py"],
                    "docs": ["Docs/feature.md"],
                    "invariants": ["Keep the fixture safe."],
                }
            },
        }
        (root / "Docs" / "subsystems.yaml").write_text(
            yaml.safe_dump(registry, sort_keys=False), encoding="utf-8"
        )

    def test_current_repository_passes(self) -> None:
        self.assertEqual(architecture_check.check_architecture(ROOT), [])

    def test_registry_rejects_missing_routed_path(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            registry_path = root / "Docs" / "subsystems.yaml"
            text = registry_path.read_text(encoding="utf-8")
            registry_path.write_text(
                text.replace("Controller/feature.py", "Controller/missing.py"),
                encoding="utf-8",
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("path does not exist" in error for error in errors))

    def test_removed_utils_module_and_import_are_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Controller" / "utils.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "Controller" / "feature.py").write_text(
                "import utils\n", encoding="utf-8"
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("must not be recreated" in error for error in errors))
            self.assertTrue(any("imports removed utils" in error for error in errors))

    def test_gui_process_termination_is_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Controller" / "GUI" / "bad.py").write_text(
                "def stop(process):\n    process.terminate()\n", encoding="utf-8"
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("GUI process termination" in error for error in errors))

    def test_signal_zero_gui_probe_is_allowed(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Controller" / "GUI" / "probe.py").write_text(
                "import os\ndef alive(pid):\n    os.kill(pid, 0)\n", encoding="utf-8"
            )

            self.assertEqual(architecture_check.check_architecture(root), [])

    def test_production_hardcoded_drive_path_is_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            drive_path = "C:" + "\\\\server"
            (root / "Controller" / "feature.py").write_text(
                f"ROOT = {drive_path!r}\n", encoding="utf-8"
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("hardcoded drive path" in error for error in errors))

    def test_unapproved_config_writer_consumer_is_rejected(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Controller" / "feature.py").write_text(
                "from Tools.server_config_editor import apply_server_config_edits\n",
                encoding="utf-8",
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("unapproved guarded" in error for error in errors))

    def test_new_source_and_test_require_registry_ownership(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            (root / "Controller" / "new_feature.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            (root / "Tests" / "test_new_feature.py").write_text(
                "# new test\n", encoding="utf-8"
            )

            errors = architecture_check.check_architecture(root)

            self.assertTrue(any("unowned source module" in error for error in errors))
            self.assertTrue(any("unowned test module" in error for error in errors))

    def test_directory_owner_covers_descendant_modules(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            registry_path = root / "Docs" / "subsystems.yaml"
            payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            payload["subsystems"]["feature"]["source"] = ["Controller"]
            payload["subsystems"]["feature"]["tests"] = ["Tests"]
            registry_path.write_text(
                yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
            )
            (root / "Controller" / "nested.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            (root / "Tests" / "test_nested.py").write_text(
                "# nested test\n", encoding="utf-8"
            )

            self.assertEqual(architecture_check.check_architecture(root), [])

    def test_explicit_legacy_directory_is_excluded(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            self._repo(root)
            legacy = root / "Controller" / "Legacy"
            legacy.mkdir()
            (legacy / "old.py").write_text("VALUE = 1\n", encoding="utf-8")

            self.assertEqual(architecture_check.check_architecture(root), [])


if __name__ == "__main__":
    unittest.main()
