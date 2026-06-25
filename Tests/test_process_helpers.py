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

from Tools import process  # noqa: E402


class ProcessHelperTests(unittest.TestCase):
    def test_exe_matching_supports_globs_and_empty_values(self) -> None:
        self.assertTrue(process._exe_matches_any("VeinServer-Win64-Test.exe", ["VeinServer-*.exe"]))
        self.assertTrue(process._exe_matches_any("VeinServer.exe", ["VeinServer.exe"]))
        self.assertFalse(process._exe_matches_any("", ["VeinServer.exe"]))
        self.assertFalse(process._exe_matches_any(None, ["VeinServer.exe"]))

    def test_cmdline_head_handles_list_and_string(self) -> None:
        self.assertEqual(
            process._cmdline_head({"cmdline": [r"C:\Game\VeinServer.exe", "-log"]}),
            r"C:\Game\VeinServer.exe",
        )
        self.assertEqual(
            process._cmdline_head({"cmdline": r'"C:\Game\VeinServer.exe" -log'}),
            r"C:\Game\VeinServer.exe",
        )
        self.assertEqual(process._cmdline_head({"cmdline": []}), "")

    def test_process_name_candidates_include_name_and_cmdline_basename(self) -> None:
        names = process._process_name_candidates(
            {"name": "python.exe", "cmdline": [r"C:\Game\VeinServer.exe"]}
        )

        self.assertEqual(names, ["python.exe", "VeinServer.exe"])

    def test_matches_known_executables_and_cwd(self) -> None:
        info = {"name": "python.exe", "cmdline": [r"C:\Game\VeinServer.exe"], "cwd": r"C:\Game"}

        self.assertTrue(process._matches_known_executables(info, ["VeinServer.exe"]))
        self.assertFalse(process._matches_known_executables(info, ["Other.exe"]))
        self.assertTrue(process._cwd_matches(info, str(Path(r"C:\Game"))))
        self.assertFalse(process._cwd_matches(info, str(Path(r"C:\Other"))))

    def test_choose_executable_returns_first_existing_candidate(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            second = server_dir / "B.exe"
            second.write_text("", encoding="utf-8")

            chosen = process._choose_executable(server_dir, ["A.exe", "B.exe"])

        self.assertEqual(chosen, second)

    def test_start_server_builds_args_and_persists_state(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            exe = server_dir / "VeinServer.exe"
            exe.write_text("", encoding="utf-8")
            pid_file = server_dir / "server.pid"
            proc = mock.Mock(pid=1234)
            proc.poll.return_value = None
            with mock.patch.object(process, "EXECUTABLE_NAMES", ["VeinServer.exe"]), mock.patch.object(
                process,
                "MAP_URL",
                "/Game/Test?listen",
            ), mock.patch.object(
                process,
                "GAME_PORT",
                7777,
            ), mock.patch.object(
                process,
                "QUERY_PORT",
                27015,
            ), mock.patch.object(
                process,
                "ENABLE_QUERY_PORT",
                True,
            ), mock.patch.object(
                process,
                "ABSOLUTE_LOG_FILE",
                "",
            ), mock.patch.object(
                process,
                "EXTRA_LAUNCH_ARGS",
                ["-BaseArg"],
            ), mock.patch.object(
                process,
                "headless_enabled",
                return_value=False,
            ), mock.patch.object(
                process.subprocess,
                "Popen",
                return_value=proc,
            ) as popen, mock.patch.object(
                process.time,
                "sleep",
            ), mock.patch.object(
                process,
                "write_flag",
            ) as write_flag, mock.patch.object(
                process,
                "PID_SERVER",
                pid_file,
            ), mock.patch.object(
                process,
                "set_server_state",
            ) as set_state, mock.patch("builtins.print"):
                result = process.start_server(
                    max_players=10,
                    ip="127.0.0.1",
                    server_dir=server_dir,
                    extra_args=["-ExtraArg"],
                )

            self.assertIs(result, proc)
            args = popen.call_args.args[0]
            self.assertIn(str(exe), args)
            self.assertIn("/Game/Test?listen", args)
            self.assertIn("-MaxPlayers=10", args)
            self.assertIn("-MultiHome=127.0.0.1", args)
            self.assertIn("-port=7777", args)
            self.assertIn("-QueryPort=27015", args)
            self.assertIn("-log", args)
            self.assertIn("-BaseArg", args)
            self.assertIn("-ExtraArg", args)
            write_flag.assert_called_once()
            self.assertEqual(pid_file.read_text(encoding="utf-8"), "1234")
            set_state.assert_called_once()

    def test_start_server_headless_falls_back_to_visible_console_when_process_exits(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            exe = server_dir / "VeinServer.exe"
            exe.write_text("", encoding="utf-8")
            pid_file = server_dir / "server.pid"
            first = mock.Mock(pid=1)
            first.poll.return_value = 1
            second = mock.Mock(pid=2)
            second.poll.return_value = None
            with mock.patch.object(process, "EXECUTABLE_NAMES", ["VeinServer.exe"]), mock.patch.object(
                process,
                "headless_enabled",
                return_value=True,
            ), mock.patch.object(
                process.subprocess,
                "Popen",
                side_effect=[first, second],
            ) as popen, mock.patch.object(
                process.time,
                "sleep",
            ), mock.patch.object(process, "write_flag"), mock.patch.object(
                process,
                "PID_SERVER",
                pid_file,
            ), mock.patch.object(process, "set_server_state"), mock.patch("builtins.print"):
                result = process.start_server(server_dir=server_dir)

            self.assertIs(result, second)
            self.assertEqual(popen.call_count, 2)
            first_args = popen.call_args_list[0].args[0]
            second_args = popen.call_args_list[1].args[0]
            self.assertNotIn("-log", first_args)
            self.assertIn("-log", second_args)


if __name__ == "__main__":
    unittest.main()
