from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "Controller" / "Tools" / "packing" / "build_gui_exe.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_gui_exe_for_test", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load packaging build script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PackagingBuildTests(unittest.TestCase):
    def test_copy_config_dir_stages_example_as_runtime_config(self) -> None:
        module = _load_build_module()
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            src = root / "Config"
            dst = root / "Bundle" / "Config"
            src.mkdir()
            (src / "config.yaml").write_text("secret: true\n", encoding="utf-8")
            (src / "config.example.yaml").write_text("secret: false\n", encoding="utf-8")

            original_root = module.REPO_ROOT
            original_template = module.CONFIG_TEMPLATE
            try:
                module.REPO_ROOT = root
                module.CONFIG_TEMPLATE = Path("Config/config.example.yaml")
                module._copy_config_dir(src, dst)
            finally:
                module.REPO_ROOT = original_root
                module.CONFIG_TEMPLATE = original_template

            self.assertEqual((dst / "config.yaml").read_text(encoding="utf-8"), "secret: false\n")
            self.assertEqual((dst / "config.example.yaml").read_text(encoding="utf-8"), "secret: false\n")

    def test_stage_bundle_excludes_local_sensitive_and_dev_files(self) -> None:
        module = _load_build_module()
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            pyinstaller_dir = root / "PyInstallerOutput"
            pyinstaller_dir.mkdir()
            (pyinstaller_dir / "VeinManager.exe").write_text("exe", encoding="utf-8")

            controller = root / "Controller"
            (controller / "Backups" / "Configs").mkdir(parents=True)
            (controller / "Backups" / "Configs" / "config-secret.yaml").write_text("secret", encoding="utf-8")
            (controller / "Legacy" / "WebAdmin").mkdir(parents=True)
            (controller / "Legacy" / "WebAdmin" / "user_accounts.json").write_text("secret", encoding="utf-8")
            (controller / "Legacy" / "WebAdmin" / "web_admin.py").write_text("ok", encoding="utf-8")

            config = root / "Config"
            (config / "Backup").mkdir(parents=True)
            (config / "Backup" / "config.json").write_text("secret", encoding="utf-8")
            (config / "config.yaml").write_text("secret: true\n", encoding="utf-8")
            (config / "config.example.yaml").write_text("secret: false\n", encoding="utf-8")

            scripts = root / "Scripts"
            scripts.mkdir()
            (scripts / "StartServer.bat").write_text("ok", encoding="utf-8")
            (scripts / "TestSuite.bat").write_text("dev", encoding="utf-8")

            (root / "Docs").mkdir()
            (root / "Docs" / "readme.md").write_text("docs", encoding="utf-8")

            bundle = root / "Bundle"
            original_root = module.REPO_ROOT
            original_template = module.CONFIG_TEMPLATE
            try:
                module.REPO_ROOT = root
                module.CONFIG_TEMPLATE = Path("Config/config.example.yaml")
                module._stage_bundle(pyinstaller_dir, bundle)
            finally:
                module.REPO_ROOT = original_root
                module.CONFIG_TEMPLATE = original_template

            self.assertFalse((bundle / "Controller" / "Backups").exists())
            self.assertFalse((bundle / "Controller" / "Legacy" / "WebAdmin" / "user_accounts.json").exists())
            self.assertTrue((bundle / "Controller" / "Legacy" / "WebAdmin" / "web_admin.py").exists())
            self.assertFalse((bundle / "Config" / "Backup").exists())
            self.assertEqual((bundle / "Config" / "config.yaml").read_text(encoding="utf-8"), "secret: false\n")
            self.assertTrue((bundle / "Scripts" / "StartServer.bat").exists())
            self.assertFalse((bundle / "Scripts" / "TestSuite.bat").exists())


if __name__ == "__main__":
    unittest.main()
