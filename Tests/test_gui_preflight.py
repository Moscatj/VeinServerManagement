from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from PySide6 import QtWidgets  # noqa: E402

from GUI import preflight  # noqa: E402
from Tools.server_config_validator import ServerConfigCheck  # noqa: E402


def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class GuiPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = app()

    def test_summarize_preflight_prioritizes_problems(self) -> None:
        payload = preflight.summarize_preflight(
            [
                ServerConfigCheck("ok", "PASS", "good"),
                ServerConfigCheck("info", "INFO", "optional"),
                ServerConfigCheck("warn", "WARN", "check this"),
                ServerConfigCheck("fail", "FAIL", "bad"),
            ]
        )

        self.assertEqual(payload["summary"]["PASS"], 1)
        self.assertEqual(payload["summary"]["INFO"], 1)
        self.assertEqual(payload["summary"]["WARN"], 1)
        self.assertEqual(payload["summary"]["FAIL"], 1)
        self.assertIn("failure", payload["headline"])
        self.assertEqual([item["name"] for item in payload["problems"]], ["info", "warn", "fail"])

    def test_worker_restores_env_and_emits_payload(self) -> None:
        worker = preflight.PreflightWorker("Config/config.example.yaml")
        snapshots: list[dict] = []
        worker.signals.ready.connect(snapshots.append)

        with mock.patch.dict(os.environ, {"VEIN_CONFIG": "old.yaml"}), mock.patch(
            "GUI.preflight.load_config_for_preflight",
            return_value={"server_dir": "Server"},
        ), mock.patch.object(
            preflight,
            "validate_server_config",
            return_value=[ServerConfigCheck("server.config.root", "WARN", "missing")],
        ):
            worker.run()
            self.assertEqual(os.environ["VEIN_CONFIG"], "old.yaml")

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["summary"]["WARN"], 1)
        self.assertEqual(snapshots[0]["summary"]["INFO"], 0)


if __name__ == "__main__":
    unittest.main()
