from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from PySide6 import QtWidgets  # noqa: E402

from GUI import status  # noqa: E402
import vein_manager  # noqa: E402


def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class StatusPollerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = app()

    def _poller(self, runtime_dir: Path) -> status.StatusPoller:
        cfg = {
            "paths": {"runtime_dir": str(runtime_dir)},
            "monitor": {"heartbeat_seconds": 10, "fresh_window_multiplier": 2.0},
            "backups": {"enabled": False, "enable": True},
        }
        with mock.patch.object(status, "load_and_validate_config", side_effect=RuntimeError("fallback")):
            return status.StatusPoller("config.yaml", lambda _: (cfg, "yaml", None))

    def test_runtime_paths_and_hb_knobs_from_fallback_config(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            poller = self._poller(Path(tmp))

            self.assertEqual(poller.hb_seconds, 10)
            self.assertEqual(poller.fresh_mult, 2.0)
            self.assertEqual(poller._runtime_paths_v2()["runtime_dir"], Path(tmp))
            self.assertEqual(poller._rt_paths_v2()["pid_log"], Path(tmp) / "log_monitor.pid")

    def test_read_helpers_and_freshness(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime_dir = Path(tmp)
            poller = self._poller(runtime_dir)
            state = runtime_dir / "log_monitor.state.json"
            state.write_text(
                json.dumps({"last_updated": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
            text = runtime_dir / "pid.txt"
            text.write_text("123", encoding="utf-8")

            self.assertEqual(poller._read_text(text), "123")
            self.assertEqual(poller._read_json(state)["last_updated"], json.loads(state.read_text())["last_updated"])
            self.assertTrue(poller._is_fresh(state, 10, 2.0))
            self.assertFalse(poller._is_fresh(runtime_dir / "missing.json", 10, 2.0))

    def test_run_emits_snapshot(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime_dir = Path(tmp)
            poller = self._poller(runtime_dir)
            (runtime_dir / "server_state.json").write_text('{"pid": 100}', encoding="utf-8")
            (runtime_dir / "log_monitor.pid").write_text("101", encoding="utf-8")
            (runtime_dir / "crash_monitor.pid").write_text("102", encoding="utf-8")
            (runtime_dir / "log_monitor.state.json").write_text(
                json.dumps({"last_updated": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
            (runtime_dir / "crash_monitor.state.json").write_text('{"status": "watching"}', encoding="utf-8")
            (runtime_dir / "backup.state.json").write_text(
                '{"last_utc": "now", "last_zip": "backup.zip", "counts": {"TOTAL": 1}, "root": "Backups"}',
                encoding="utf-8",
            )
            snapshots: list[dict] = []
            finished: list[bool] = []
            poller.signals.ready.connect(snapshots.append)
            poller.signals.finished.connect(lambda: finished.append(True))
            poller._load_any_config = mock.Mock(
                side_effect=AssertionError("worker must not parse YAML")
            )
            with mock.patch.object(poller, "_pid_alive", return_value=True):
                poller.run()

        self.assertEqual(len(snapshots), 1)
        snap = snapshots[0]
        self.assertTrue(snap["server"])
        self.assertTrue(snap["logmon"])
        self.assertTrue(snap["logmon_fresh"])
        self.assertTrue(snap["crashmon"])
        self.assertEqual(snap["crash_mode"], "watching")
        self.assertFalse(snap["backup"]["enabled"])
        self.assertEqual(snap["backup"]["last_zip"], "backup.zip")
        self.assertFalse(snap["server_available"])
        self.assertEqual(finished, [True])
        poller._load_any_config.assert_not_called()

    def test_main_allows_only_one_status_worker_at_a_time(self) -> None:
        class Signal:
            def __init__(self) -> None:
                self.callback = None

            def connect(self, callback) -> None:
                self.callback = callback

        class Signals:
            def __init__(self) -> None:
                self.ready = Signal()
                self.finished = Signal()

        worker = mock.Mock()
        worker.signals = Signals()
        owner = mock.Mock()
        owner._poller = None
        owner.config_path = "config.yaml"
        owner._apply_status_snapshot = mock.Mock()
        owner._status_poll_finished = lambda: setattr(owner, "_poller", None)

        with mock.patch.object(vein_manager, "StatusPoller", return_value=worker) as factory:
            vein_manager.Main._kick_status_poll(owner)
            vein_manager.Main._kick_status_poll(owner)

        factory.assert_called_once()
        owner._pool.start.assert_called_once_with(worker)
        self.assertIs(owner._poller, worker)
        assert worker.signals.finished.callback is not None
        worker.signals.finished.callback()
        self.assertIsNone(owner._poller)


if __name__ == "__main__":
    unittest.main()
