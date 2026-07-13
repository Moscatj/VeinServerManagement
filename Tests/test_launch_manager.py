from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "Controller" / "launch_manager.py"
START_SCRIPT = ROOT / "Scripts" / "Start_VeinManager.bat"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("launch_manager_for_test", LAUNCHER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load launch_manager.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LaunchManagerTests(unittest.TestCase):
    def test_bootstrap_failure_is_written_under_repo_logs(self) -> None:
        module = _load_launcher()
        with TemporaryDirectory(dir=ROOT) as temp_dir:
            module.BOOTSTRAP_LOG_DIR = Path(temp_dir) / "Logs" / "gui" / "bootstrap"
            path = module._write_bootstrap_failure(RuntimeError("startup failed"))

            self.assertIsNotNone(path)
            assert path is not None
            self.assertIn("startup failed", path.read_text(encoding="utf-8"))

    def test_main_reports_pre_gui_import_failure(self) -> None:
        module = _load_launcher()
        failure = RuntimeError("missing GUI dependency")
        with (
            mock.patch.dict(sys.modules, {"vein_manager": None}),
            mock.patch.object(module, "_write_bootstrap_failure", return_value=None) as write_log,
            mock.patch.object(module, "_show_bootstrap_failure") as show_error,
        ):
            result = module.main()

        self.assertEqual(result, 1)
        write_log.assert_called_once()
        show_error.assert_called_once()
        self.assertIsInstance(show_error.call_args.args[0], ModuleNotFoundError)

    def test_batch_launcher_uses_bootstrap_and_safe_errorlevel_checks(self) -> None:
        text = START_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("launch_manager.py", text)
        self.assertIn("if not errorlevel 1", text)
        self.assertNotIn("if %ERRORLEVEL%==0", text)
        self.assertIn("Logs\\gui\\bootstrap", text)
        self.assertIn('if /i "%~1"=="__PROBE__"', text)
        self.assertIn("--startup-probe", text)


if __name__ == "__main__":
    unittest.main()
