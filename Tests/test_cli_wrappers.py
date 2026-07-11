from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

import logcat  # noqa: E402
import log_summary  # noqa: E402
import migrate_mgmt_logs  # noqa: E402
import vein_tools  # noqa: E402


class CliWrapperTests(unittest.TestCase):
    def test_logcat_list_and_search_paths(self) -> None:
        with mock.patch("sys.argv", ["logcat", "--list"]), mock.patch.object(
            logcat.mgmt_logs,
            "available_subsystems",
            return_value=["gui"],
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(logcat.main(), 0)
        printed.assert_called_with("gui")

        hit = mock.Mock()
        with mock.patch("sys.argv", ["logcat", "--search", "error"]), mock.patch.object(
            logcat.log_search,
            "search_logs",
            return_value=[hit],
        ), mock.patch.object(
            logcat.log_search,
            "format_hits",
            return_value="formatted",
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(logcat.main(), 0)
        printed.assert_called_with("formatted")

    def test_logcat_reports_no_matches_and_passes_search_options(self) -> None:
        with mock.patch(
            "sys.argv",
            [
                "logcat",
                "--subsystem",
                " monitor_log ",
                "--subsystem",
                "",
                "--search",
                "timeout",
                "--since",
                "2h",
                "--limit",
                "7",
                "--case-sensitive",
                "--include-archive",
            ],
        ), mock.patch.object(
            logcat.log_search,
            "parse_since",
            return_value=123.0,
        ) as parse_since, mock.patch.object(
            logcat.log_search,
            "search_logs",
            return_value=[],
        ) as search, mock.patch(
            "builtins.print"
        ) as printed:
            self.assertEqual(logcat.main(), 0)

        parse_since.assert_called_once_with("2h")
        search.assert_called_once_with(
            subsystems=["monitor_log"],
            pattern="timeout",
            case_sensitive=True,
            since_ts=123.0,
            max_hits=7,
            include_archive=True,
        )
        printed.assert_called_once_with("No matches.")

    def test_log_summary_serializes_events_and_writes_summary(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            log_file = root / "gui" / "app.log"
            log_file.parent.mkdir()
            event = log_summary.log_events.LogEvent(
                file=log_file,
                line_no=2,
                level="ERROR",
                message="failed",
                timestamp=1.0,
            )
            with mock.patch.object(log_summary.mgmt_logs, "management_log_root", return_value=root), mock.patch.object(
                log_summary.mgmt_logs,
                "subsystem_dir",
                return_value=root / "gui",
            ), mock.patch.object(
                log_summary.log_events,
                "collect_recent_events",
                return_value=[event],
            ):
                payload = log_summary.summarize_subsystem("gui", limit=10, per_file=5)

        self.assertEqual(payload["events"][0]["file"], str(Path("gui") / "app.log"))
        self.assertEqual(payload["events"][0]["level"], "ERROR")

    def test_migrate_mgmt_logs_reports_no_moves(self) -> None:
        with mock.patch("sys.argv", ["migrate_mgmt_logs", "--dry-run"]), mock.patch.object(
            migrate_mgmt_logs.mgmt_logs,
            "migrate_legacy_logs",
            return_value=[],
        ), mock.patch("builtins.print") as printed:
            self.assertEqual(migrate_mgmt_logs.main(), 0)
        printed.assert_called_with("No legacy logs found in Logs/.")

    def test_migrate_mgmt_logs_reports_dry_run_and_real_moves(self) -> None:
        moves = [(Path("Logs/server.stdout.log"), Path("Logs/start_server/server.stdout.log"))]

        with mock.patch("sys.argv", ["migrate_mgmt_logs", "--dry-run"]), mock.patch.object(
            migrate_mgmt_logs.mgmt_logs,
            "migrate_legacy_logs",
            return_value=moves,
        ) as migrate, mock.patch("builtins.print") as printed:
            self.assertEqual(migrate_mgmt_logs.main(), 0)

        migrate.assert_called_once_with(dry_run=True)
        printed.assert_any_call(
            f"Would move: {moves[0][0]} -> {moves[0][1]}"
        )
        printed.assert_any_call("Would move 1 file(s).")

        with mock.patch("sys.argv", ["migrate_mgmt_logs"]), mock.patch.object(
            migrate_mgmt_logs.mgmt_logs,
            "migrate_legacy_logs",
            return_value=moves,
        ) as migrate, mock.patch("builtins.print") as printed:
            self.assertEqual(migrate_mgmt_logs.main(), 0)

        migrate.assert_called_once_with(dry_run=False)
        printed.assert_any_call(f"Moved: {moves[0][0]} -> {moves[0][1]}")
        printed.assert_any_call("Moved 1 file(s).")

    def test_vein_tools_restart_runs_stop_then_start(self) -> None:
        stop = mock.Mock()
        start = mock.Mock()
        stop.run.return_value = 0
        start.run.return_value = 0
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text("version: 2\n", encoding="utf-8")
            commands = dict(vein_tools.COMMANDS)
            commands["stop-server"] = stop
            commands["start-server"] = start
            with mock.patch.object(vein_tools, "COMMANDS", commands), mock.patch.object(
                vein_tools.time if hasattr(vein_tools, "time") else __import__("time"),
                "sleep",
            ):
                code = vein_tools.main(["restart-server", "--config", str(cfg), "--restart-delay", "0"])

        self.assertEqual(code, 0)
        stop.run.assert_called_once()
        start.run.assert_called_once()

    def test_vein_tools_explicit_config_overrides_inherited_environment(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            cfg = (Path(tmp) / "selected.yaml").resolve()
            cfg.write_text("version: 2\n", encoding="utf-8")
            command = mock.Mock()
            command.run.return_value = 0
            commands = dict(vein_tools.COMMANDS)
            commands["health-check"] = command
            with mock.patch.object(vein_tools, "COMMANDS", commands), mock.patch.dict(
                os.environ, {"VEIN_CONFIG": str(ROOT / "stale.yaml")}
            ):
                code = vein_tools.main(["health-check", "--config", str(cfg)])
                selected = os.environ["VEIN_CONFIG"]

        self.assertEqual(code, 0)
        self.assertEqual(selected, str(cfg))

    def test_vein_tools_health_check_command_dispatches(self) -> None:
        command = vein_tools.COMMANDS["health-check"]
        with mock.patch("Tools.health_check.main", return_value=0) as health_main:
            self.assertEqual(command.run(), 0)
        health_main.assert_called_once()

    def test_vein_tools_server_config_check_command_dispatches(self) -> None:
        command = vein_tools.COMMANDS["server-config-check"]
        with mock.patch("Tools.server_config_validator.main", return_value=0) as check_main:
            self.assertEqual(command.run(), 0)
        check_main.assert_called_once()

    def test_vein_tools_subcommand_does_not_leak_wrapper_argv(self) -> None:
        seen: list[list[str]] = []

        def fake_main() -> int:
            seen.append(list(sys.argv))
            return 0

        command = vein_tools.CommandSpec("Tools.health_check", "main", "Run health check")
        with mock.patch("Tools.health_check.main", side_effect=fake_main), mock.patch(
            "sys.argv",
            ["VeinTools.exe", "health-check"],
        ):
            self.assertEqual(command.run(), 0)

        self.assertEqual(seen, [["VeinTools.exe"]])

    def test_vein_tools_exposes_uninstall_cleanup_command(self) -> None:
        command = vein_tools.COMMANDS["uninstall-cleanup"]

        self.assertEqual(command.module, "Tools.uninstall_cleanup")
        self.assertEqual(command.attr, "main")


if __name__ == "__main__":
    unittest.main()
