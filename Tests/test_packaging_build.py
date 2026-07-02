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


if __name__ == "__main__":
    unittest.main()
