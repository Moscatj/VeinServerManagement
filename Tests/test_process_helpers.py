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


class FakeProcess:
    def __init__(self, pid: int, info: dict | None = None) -> None:
        self.pid = pid
        self.info = info or {}
        self.terminated = False
        self.killed = False
        self.wait_timeout: int | None = None
        self._running = True
        self._children: list[FakeProcess] = []

    def children(self, recursive: bool = False) -> list["FakeProcess"]:
        return list(self._children)

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int | None = None) -> None:
        self.wait_timeout = timeout
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def kill(self) -> None:
        self.killed = True
        self._running = False


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

    def test_cmdline_helpers_tolerate_invalid_values(self) -> None:
        with mock.patch.object(process.shlex, "split", side_effect=ValueError("bad")):
            self.assertEqual(process._cmdline_head({"cmdline": '"unterminated'}), "")

        self.assertEqual(process._cmdline_head_basename({"cmdline": []}), "")
        with mock.patch.object(process.Path, "resolve", side_effect=OSError("bad")):
            self.assertTrue(process._cmdline_head_fullpath({"cmdline": ["VeinServer.exe"]}))

    def test_list_all_servers_filters_known_images(self) -> None:
        match = FakeProcess(1, {"name": "VeinServer-Win64-Test.exe", "cmdline": []})
        miss = FakeProcess(2, {"name": "notepad.exe", "cmdline": []})

        with mock.patch.object(process.psutil, "process_iter", return_value=[match, miss]), mock.patch(
            "builtins.print"
        ):
            found = process.list_all_servers(verbose=True)

        self.assertEqual(found, [match])

    def test_list_all_servers_ignores_inaccessible_processes(self) -> None:
        bad = mock.Mock()
        type(bad).info = mock.PropertyMock(side_effect=process.psutil.AccessDenied(pid=5))
        match = FakeProcess(6, {"name": "VeinServer.exe", "cmdline": []})

        with mock.patch.object(process.psutil, "process_iter", return_value=[bad, match]):
            self.assertEqual(process.list_all_servers(), [match])

    def test_find_running_server_prefers_matching_cwd_and_known_name(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp).resolve()
            match = FakeProcess(
                10,
                {
                    "name": "wrapper.exe",
                    "cmdline": [str(server_dir / "VeinServer.exe")],
                    "cwd": str(server_dir),
                },
            )
            miss = FakeProcess(11, {"name": "VeinServer.exe", "cmdline": [], "cwd": str(ROOT)})

            with mock.patch.object(process.psutil, "process_iter", return_value=[miss, match]):
                found = process.find_running_server(["VeinServer.exe"], server_dir)

        self.assertIs(found, match)

    def test_find_running_server_falls_back_to_name_and_pattern(self) -> None:
        name_match = FakeProcess(20, {"name": "VeinServer.exe", "cmdline": []})
        pattern_match = FakeProcess(21, {"name": "VeinServer-Win64-Shipping.exe", "cmdline": []})

        with mock.patch.object(
            process.psutil,
            "process_iter",
            side_effect=[
                [],
                [name_match],
            ],
        ):
            self.assertIs(process.find_running_server(["VeinServer.exe"], ROOT), name_match)

        with mock.patch.object(
            process.psutil,
            "process_iter",
            side_effect=[
                [],
                [],
                [pattern_match],
            ],
        ):
            self.assertIs(process.find_running_server(["Other.exe"], ROOT), pattern_match)

    def test_find_running_server_ignores_access_denied_candidates(self) -> None:
        denied = FakeProcess(1, {"name": "VeinServer.exe", "cmdline": []})
        with mock.patch.object(process, "_cwd_matches", side_effect=[process.psutil.AccessDenied(pid=1), False]), mock.patch.object(
            process,
            "_matches_known_executables",
            return_value=True,
        ), mock.patch.object(
            process.psutil,
            "process_iter",
            side_effect=[[denied], [denied], []],
        ):
            self.assertIs(process.find_running_server(["VeinServer.exe"], ROOT), denied)

    def test_is_vein_server_process_returns_false_for_inaccessible_info(self) -> None:
        denied = mock.Mock()
        type(denied).info = mock.PropertyMock(side_effect=process.psutil.AccessDenied(pid=1))
        match = FakeProcess(22, {"name": "VeinServer.exe", "cmdline": []})

        self.assertFalse(process._is_vein_server_process(denied))
        self.assertTrue(process._is_vein_server_process(match))

    def test_kill_process_tree_terminates_then_kills_remaining_processes(self) -> None:
        parent = FakeProcess(100)
        child = FakeProcess(101)
        parent._children = [child]

        with mock.patch.object(process.psutil, "Process", return_value=parent), mock.patch.object(
            process.psutil,
            "wait_procs",
        ):
            process.kill_process_tree(100, timeout=1)

        self.assertTrue(parent.terminated)
        self.assertTrue(child.terminated)
        self.assertTrue(parent.killed)
        self.assertTrue(child.killed)

    def test_kill_process_tree_returns_when_parent_unavailable(self) -> None:
        with mock.patch.object(
            process.psutil,
            "Process",
            side_effect=process.psutil.NoSuchProcess(pid=999),
        ), mock.patch.object(process.psutil, "wait_procs") as wait_procs:
            process.kill_process_tree(999)

        wait_procs.assert_not_called()

    def test_kill_process_tree_tolerates_terminate_and_kill_errors(self) -> None:
        parent = FakeProcess(100)
        child = FakeProcess(101)
        parent._children = [child]
        parent.terminate = mock.Mock(side_effect=RuntimeError("terminate failed"))
        child.kill = mock.Mock(side_effect=RuntimeError("kill failed"))

        with mock.patch.object(process.psutil, "Process", return_value=parent), mock.patch.object(
            process.psutil,
            "wait_procs",
        ):
            process.kill_process_tree(100, timeout=1)

        parent.terminate.assert_called_once()
        child.kill.assert_called_once()

    def test_stop_server_clears_markers_when_no_process_is_running(self) -> None:
        with mock.patch.object(process, "find_running_server", return_value=None), mock.patch.object(
            process,
            "clear_runtime_markers",
        ) as clear_markers:
            self.assertTrue(process.stop_server())

        clear_markers.assert_called_once()

    def test_stop_server_graceful_wait_updates_state(self) -> None:
        proc = FakeProcess(222)

        with mock.patch.object(process, "find_running_server", return_value=proc), mock.patch.object(
            process,
            "send_discord_message",
        ) as discord, mock.patch.object(
            process,
            "clear_runtime_markers",
        ) as clear_markers, mock.patch.object(
            process,
            "set_server_state",
        ) as set_state:
            self.assertTrue(process.stop_server(timeout=3))

        self.assertTrue(proc.terminated)
        self.assertEqual(proc.wait_timeout, 3)
        discord.assert_called_once()
        clear_markers.assert_called_once()
        set_state.assert_called_once_with(False, pid=0, last_exit_code=0)

    def test_stop_server_forces_taskkill_when_graceful_wait_fails(self) -> None:
        proc = FakeProcess(333)
        proc.wait = mock.Mock(side_effect=TimeoutError("still running"))

        with mock.patch.object(process, "find_running_server", return_value=proc), mock.patch.object(
            process,
            "send_discord_message",
        ), mock.patch.object(process, "clear_runtime_markers") as clear_markers, mock.patch.object(
            process,
            "set_server_state",
        ) as set_state, mock.patch.object(
            process.subprocess,
            "run",
        ) as run:
            self.assertTrue(process.stop_server(timeout=1))

        run.assert_called_once()
        clear_markers.assert_called_once()
        set_state.assert_called_once_with(False, pid=0, last_exit_code=-1)

    def test_stop_server_returns_false_when_force_taskkill_fails(self) -> None:
        proc = FakeProcess(334)
        proc.wait = mock.Mock(side_effect=TimeoutError("still running"))

        with mock.patch.object(process, "find_running_server", return_value=proc), mock.patch.object(
            process,
            "send_discord_message",
        ), mock.patch.object(
            process.subprocess,
            "run",
            side_effect=OSError("taskkill missing"),
        ):
            self.assertFalse(process.stop_server(timeout=1))

    def test_stop_all_servers_aggressive_returns_acted_pids_and_clears_state(self) -> None:
        proc = FakeProcess(444, {"name": "VeinServer.exe", "cmdline": ["VeinServer.exe"]})

        with mock.patch.object(process, "list_all_servers", side_effect=[[proc], []]), mock.patch.object(
            process,
            "send_discord_message",
        ) as discord, mock.patch.object(process, "kill_process_tree") as kill_tree, mock.patch.object(
            process.subprocess,
            "run",
        ), mock.patch.object(
            process,
            "clear_runtime_markers",
        ) as clear_markers, mock.patch.object(
            process,
            "set_server_state",
        ) as set_state:
            acted = process.stop_all_servers_aggressive()

        self.assertEqual(acted, [444])
        discord.assert_called_once()
        kill_tree.assert_called_once_with(444, timeout=mock.ANY)
        clear_markers.assert_called_once()
        set_state.assert_called_once_with(False, pid=0, last_exit_code=-1)

    def test_stop_all_servers_aggressive_returns_empty_when_no_processes(self) -> None:
        with mock.patch.object(process, "list_all_servers", return_value=[]), mock.patch.object(
            process,
            "send_discord_message",
        ) as discord:
            self.assertEqual(process.stop_all_servers_aggressive(), [])

        discord.assert_not_called()

    def test_stop_all_servers_aggressive_uses_taskkill_fallback_and_leftover_paths(self) -> None:
        proc = FakeProcess(445, {"name": "VeinServer.exe", "cmdline": ["VeinServer.exe"]})
        leftover = FakeProcess(
            446,
            {
                "name": "VeinServer.exe",
                "cmdline": [str(ROOT / "VeinServer.exe")],
            },
        )

        with mock.patch.object(process, "list_all_servers", side_effect=[[proc], [leftover]]), mock.patch.object(
            process,
            "send_discord_message",
        ), mock.patch.object(
            process,
            "kill_process_tree",
            side_effect=RuntimeError("kill tree failed"),
        ), mock.patch.object(
            process.subprocess,
            "run",
        ) as run, mock.patch.object(
            process,
            "_powershell_kill_by_fullpaths",
        ) as powershell, mock.patch.object(
            process,
            "clear_runtime_markers",
        ), mock.patch.object(
            process,
            "set_server_state",
        ):
            acted = process.stop_all_servers_aggressive()

        self.assertEqual(acted, [445])
        self.assertGreaterEqual(run.call_count, 1)
        powershell.assert_called_once()
        self.assertIn(str((ROOT / "VeinServer.exe").resolve()), powershell.call_args.args[0])

    def test_powershell_kill_by_fullpaths_skips_empty_and_swallows_errors(self) -> None:
        with mock.patch.object(process.subprocess, "run") as run:
            process._powershell_kill_by_fullpaths([])
        run.assert_not_called()

        with mock.patch.object(process.subprocess, "run", side_effect=OSError("no powershell")):
            process._powershell_kill_by_fullpaths([r"C:\Game\VeinServer.exe"])

    def test_runtime_and_headless_helpers_cover_error_paths(self) -> None:
        flags = process.win_creationflags_for_headless()
        self.assertIsInstance(flags, int)
        self.assertGreaterEqual(flags, 0)

        bad_config = mock.Mock()
        bad_config.get.side_effect = RuntimeError("bad config")
        with mock.patch.object(process, "config", bad_config):
            self.assertFalse(process.headless_enabled())
            self.assertFalse(process.current_headless_flag())

        with mock.patch.object(process, "find_running_server", return_value=object()):
            self.assertTrue(process.is_server_running())
        with mock.patch.object(process, "find_running_server", return_value=None):
            self.assertFalse(process.is_server_running())

    def test_merged_launch_args_preserves_base_order_and_adds_new_values(self) -> None:
        with mock.patch.object(process, "EXTRA_LAUNCH_ARGS", ["-A", "-B"]):
            self.assertEqual(process._merged_launch_args(["-B", "-C"]), ["-A", "-B", "-C"])
            self.assertEqual(process._merged_launch_args(None), ["-A", "-B"])

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

    def test_start_server_supports_explicit_executable_cwd_abslog_and_runtime_write_failure(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            exe = base / "CustomServer.exe"
            exe.write_text("", encoding="utf-8")
            cwd = base / "Work"
            cwd.mkdir()
            proc = mock.Mock(pid=9876)
            proc.poll.return_value = None

            with mock.patch.object(process, "MAP_URL", ""), mock.patch.object(
                process,
                "GAME_PORT",
                0,
            ), mock.patch.object(
                process,
                "QUERY_PORT",
                27015,
            ), mock.patch.object(
                process,
                "ENABLE_QUERY_PORT",
                False,
            ), mock.patch.object(
                process,
                "ABSOLUTE_LOG_FILE",
                str(base / "Vein.log"),
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
                side_effect=OSError("state write failed"),
            ), mock.patch(
                "builtins.print"
            ) as printed:
                result = process.start_server(
                    max_players=0,
                    ip="0.0.0.0",
                    executable=str(exe),
                    cwd=cwd,
                )

            self.assertIs(result, proc)
            args = popen.call_args.args[0]
            self.assertEqual(args[0], str(exe))
            self.assertNotIn("-MaxPlayers=0", args)
            self.assertNotIn("-MultiHome=0.0.0.0", args)
            self.assertNotIn("-port=0", args)
            self.assertNotIn("-QueryPort=27015", args)
            self.assertIn(f"-Abslog={base / 'Vein.log'}", args)
            self.assertEqual(popen.call_args.kwargs["cwd"], str(cwd))
            self.assertTrue(any("failed to persist runtime state" in str(call) for call in printed.call_args_list))

    def test_start_server_returns_none_when_no_executable_exists(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp, mock.patch.object(
            process,
            "EXECUTABLE_NAMES",
            ["Missing.exe"],
        ), mock.patch("builtins.print") as printed:
            result = process.start_server(server_dir=Path(tmp))

        self.assertIsNone(result)
        printed.assert_called_once()

    def test_start_server_returns_none_when_popen_fails(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            exe = server_dir / "VeinServer.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.object(process, "EXECUTABLE_NAMES", ["VeinServer.exe"]), mock.patch.object(
                process,
                "headless_enabled",
                return_value=False,
            ), mock.patch.object(
                process.subprocess,
                "Popen",
                side_effect=OSError("nope"),
            ), mock.patch("builtins.print"):
                self.assertIsNone(process.start_server(server_dir=server_dir))

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

    def test_start_vein_server_and_resolve_executable_aliases(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            server_dir = Path(tmp)
            exe = server_dir / "VeinServer.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.object(process, "start_server", return_value="started") as start:
                self.assertEqual(process.start_vein_server(max_players=2), "started")

            start.assert_called_once_with(max_players=2)
            self.assertEqual(
                process.resolve_server_executable(server_dir, ["VeinServer.exe"]),
                exe,
            )


if __name__ == "__main__":
    unittest.main()
