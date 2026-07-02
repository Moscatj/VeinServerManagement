from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import uninstall_cleanup  # noqa: E402


class UninstallCleanupTests(unittest.TestCase):
    def test_cleanup_stops_monitors_without_server_shutdown_when_server_absent(self) -> None:
        with mock.patch.object(uninstall_cleanup, "stop_all_monitors") as stop_monitors, mock.patch.object(
            uninstall_cleanup,
            "_list_running_servers",
            return_value=[],
        ):
            self.assertEqual(uninstall_cleanup.cleanup_for_uninstall(), 0)

        stop_monitors.assert_called_once_with()

    def test_cleanup_runs_controlled_shutdown_when_server_is_running(self) -> None:
        fake_shutdown = types.SimpleNamespace(main=mock.Mock())
        original = sys.modules.get("shutdown_server")
        sys.modules["shutdown_server"] = fake_shutdown
        try:
            with mock.patch.object(uninstall_cleanup, "stop_all_monitors") as stop_monitors, mock.patch.object(
                uninstall_cleanup,
                "_list_running_servers",
                return_value=[object()],
            ):
                self.assertEqual(uninstall_cleanup.cleanup_for_uninstall(), 0)
        finally:
            if original is None:
                sys.modules.pop("shutdown_server", None)
            else:
                sys.modules["shutdown_server"] = original

        stop_monitors.assert_called_once_with()
        fake_shutdown.main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
