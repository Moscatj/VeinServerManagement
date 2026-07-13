from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "Controller"
if str(CONTROLLER) not in sys.path:
    sys.path.insert(0, str(CONTROLLER))

from Tools import steamcmd_runner  # noqa: E402


class _FakeProcess:
    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return steamcmd_runner.CANCELLED_EXIT_CODE if self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return steamcmd_runner.CANCELLED_EXIT_CODE


class _CompletedProcess:
    def __init__(self) -> None:
        self.stdout = io.StringIO("")

    def poll(self) -> int:
        return 0

    def wait(self, timeout: float | None = None) -> int:
        return 0


class SteamCmdRunnerTests(unittest.TestCase):
    def test_bootstrap_command_initializes_steamcmd_without_server_arguments(self) -> None:
        command = steamcmd_runner.build_bootstrap_command(Path("C:/tools/steamcmd.exe"))

        self.assertEqual(command, ["C:\\tools\\steamcmd.exe", "+quit"])

    def test_build_command_uses_fixed_windows_public_validation_flow(self) -> None:
        command = steamcmd_runner.build_command(
            Path("C:/tools/steamcmd.exe"), Path("D:/servers/Vein"), "2131400"
        )

        self.assertEqual(command[0], "C:\\tools\\steamcmd.exe")
        self.assertIn("+@sSteamCmdForcePlatformType", command)
        self.assertIn("+force_install_dir", command)
        self.assertIn("anonymous", command)
        self.assertEqual(command[-5:], ["2131400", "-beta", "public", "validate", "+quit"])

    def test_cancel_stops_only_the_process_created_by_the_runner(self) -> None:
        captured = io.StringIO()
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            steamcmd = root / "steamcmd.exe"
            steamcmd.touch()
            cancel_file = root / "cancel.request"
            cancel_file.write_text("cancel", encoding="utf-8")
            process = _FakeProcess()

            with (
                mock.patch.object(
                    steamcmd_runner.subprocess, "Popen", return_value=process
                ) as popen,
                redirect_stdout(captured),
            ):
                result = steamcmd_runner.run_steamcmd(
                    steamcmd, root / "Server", "2131400", cancel_file
                )

        self.assertEqual(result, steamcmd_runner.CANCELLED_EXIT_CODE)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0][0], str(steamcmd.resolve()))
        self.assertIn(steamcmd_runner.HEARTBEAT_LINE, captured.getvalue())
        self.assertIn("SteamCMD operation cancelled", captured.getvalue())

    def test_missing_steamcmd_is_reported_without_starting_a_process(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, mock.patch.object(
            steamcmd_runner.subprocess, "Popen"
        ) as popen:
            root = Path(folder)
            result = steamcmd_runner.run_steamcmd(
                root / "missing.exe", root / "Server", "2131400", root / "cancel"
            )

        self.assertEqual(result, 2)
        popen.assert_not_called()

    def test_successful_run_initializes_steamcmd_before_server_install(self) -> None:
        captured = io.StringIO()
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            steamcmd = root / "steamcmd.exe"
            steamcmd.touch()
            with (
                mock.patch.object(
                    steamcmd_runner.subprocess,
                    "Popen",
                    side_effect=[_CompletedProcess(), _CompletedProcess()],
                ) as popen,
                redirect_stdout(captured),
            ):
                result = steamcmd_runner.run_steamcmd(
                    steamcmd, root / "Server", "2131400", root / "cancel.request"
                )

        self.assertEqual(result, 0)
        self.assertEqual(popen.call_count, 2)
        self.assertEqual(popen.call_args_list[0].args[0][-1], "+quit")
        self.assertIn("+app_update", popen.call_args_list[1].args[0])
        self.assertIn(f"{steamcmd_runner.PHASE_PREFIX}bootstrap", captured.getvalue())
        self.assertIn(f"{steamcmd_runner.PHASE_PREFIX}server", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
