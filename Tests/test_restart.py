from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import restart  # noqa: E402


class RestartTests(unittest.TestCase):
    def test_initiate_controlled_restart_throttles_recent_restart(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            stamp = Path(tmp) / "last_restart_at.txt"
            lock = Path(tmp) / "restart.lock"
            stamp.write_text("100", encoding="utf-8")
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart,
                "RESTARTING_LOCK",
                lock,
            ), mock.patch.object(
                restart.time,
                "time",
                return_value=150,
            ), mock.patch.dict(
                restart.config,
                {"restart_throttle_seconds": 120},
                clear=False,
            ), mock.patch.object(restart.subprocess, "Popen") as popen, mock.patch(
                "builtins.print"
            ):
                self.assertFalse(restart.initiate_controlled_restart("test"))

        popen.assert_not_called()

    def test_existing_restart_lock_is_not_removed_by_competing_request(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            stamp = base / "last_restart_at.txt"
            lock = base / "restart.lock"
            lock.write_text("first-request", encoding="utf-8")
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart, "RESTARTING_LOCK", lock
            ), mock.patch.object(restart.subprocess, "Popen") as popen:
                self.assertFalse(restart.initiate_controlled_restart("second-request"))

            self.assertEqual(lock.read_text(encoding="utf-8"), "first-request")

        popen.assert_not_called()

    def test_spawn_failure_returns_false_without_stamp_and_cleans_owned_lock(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            stamp = base / "last_restart_at.txt"
            lock = base / "restart.lock"
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart, "RESTARTING_LOCK", lock
            ), mock.patch.object(
                restart, "win_creationflags_for_headless", return_value=0
            ), mock.patch.object(
                restart, "send_discord_message"
            ), mock.patch.object(
                restart.subprocess, "Popen", side_effect=OSError("spawn failed")
            ), mock.patch("builtins.print") as output:
                self.assertFalse(restart.initiate_controlled_restart("test"))

            self.assertFalse(lock.exists())
            self.assertFalse(stamp.exists())

        output.assert_any_call("[Restart] Failed to launch controlled restart: spawn failed")

    def test_notification_failure_does_not_block_restart(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            stamp = base / "last_restart_at.txt"
            lock = base / "restart.lock"
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart, "RESTARTING_LOCK", lock
            ), mock.patch.object(restart.time, "time", return_value=3_000), mock.patch.object(
                restart.time, "sleep"
            ), mock.patch.dict(
                restart.config, {"restart_settle_seconds": 0}, clear=False
            ), mock.patch.object(
                restart, "win_creationflags_for_headless", return_value=0
            ), mock.patch.object(
                restart, "send_discord_message", side_effect=RuntimeError("offline")
            ), mock.patch.object(restart.subprocess, "Popen") as popen, mock.patch(
                "builtins.print"
            ):
                self.assertTrue(restart.initiate_controlled_restart("test"))

            self.assertFalse(lock.exists())
            self.assertEqual(stamp.read_text(encoding="utf-8"), "3000")

        popen.assert_called_once()

    def test_initiate_controlled_restart_spawns_and_cleans_lock(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            stamp = Path(tmp) / "last_restart_at.txt"
            lock = Path(tmp) / "restart.lock"
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart,
                "RESTARTING_LOCK",
                lock,
            ), mock.patch.object(
                restart.time,
                "time",
                return_value=1_000,
            ), mock.patch.object(
                restart.time,
                "sleep",
            ), mock.patch.dict(
                restart.config,
                {"restart_throttle_seconds": 120, "restart_settle_seconds": 0},
                clear=False,
            ), mock.patch.object(
                restart,
                "win_creationflags_for_headless",
                return_value=0,
            ), mock.patch.object(
                restart,
                "send_discord_message",
            ) as send, mock.patch.object(
                restart.subprocess,
                "Popen",
            ) as popen, mock.patch("builtins.print"):
                self.assertTrue(restart.initiate_controlled_restart("test"))

            self.assertFalse(lock.exists())
            self.assertEqual(stamp.read_text(encoding="utf-8"), "1000")

        popen.assert_called_once()
        send.assert_called_once()

    def test_packaged_restart_uses_vein_tools_subcommand(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            stamp = base / "last_restart_at.txt"
            lock = base / "restart.lock"
            with mock.patch.object(restart, "RESTART_STAMP", stamp), mock.patch.object(
                restart, "RESTARTING_LOCK", lock
            ), mock.patch.object(restart.time, "time", return_value=2_000), mock.patch.object(
                restart.time, "sleep"
            ), mock.patch.dict(
                restart.config,
                {"restart_throttle_seconds": 120, "restart_settle_seconds": 0},
                clear=False,
            ), mock.patch.object(restart, "win_creationflags_for_headless", return_value=0), mock.patch.object(
                restart, "send_discord_message"
            ), mock.patch.object(restart.subprocess, "Popen") as popen, mock.patch.object(
                restart.sys, "frozen", True, create=True
            ), mock.patch.object(
                restart.sys, "executable", str(base / "VeinTools.exe")
            ), mock.patch.dict(
                restart.os.environ, {"VEIN_CONFIG": str(base / "Config" / "config.yaml")}, clear=False
            ):
                self.assertTrue(restart.initiate_controlled_restart("packaged"))

        command = popen.call_args.args[0]
        self.assertEqual(command[1], "start-server")
        self.assertIn("--config", command)


if __name__ == "__main__":
    unittest.main()
