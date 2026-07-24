from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

import monitor_log  # noqa: E402

SANITIZED_LOG_FIXTURE = ROOT / "Tests" / "fixtures" / "vein_log_events_sanitized.txt"


class MonitorLogStateTests(unittest.TestCase):
    def setUp(self) -> None:
        monitor_log._PLAYER_CACHE.clear()
        monitor_log._NAME_TO_ID.clear()
        monitor_log._ID_TO_NAME.clear()
        monitor_log._LAST_DISCONNECT_NOTIFY.clear()

    def test_state_explains_waiting_path_on_clean_install(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            runtime = Path(tmp)
            state = runtime / "log_monitor.state.json"
            expected = runtime / "Server" / "Vein" / "Saved" / "Logs" / "Vein.log"
            runtime_paths = {
                "runtime": runtime,
                "state_log": state,
                "pid_log": runtime / "log_monitor.pid",
                "stop_log": runtime / "stop_log_monitor.flag",
            }
            with mock.patch.object(monitor_log, "_runtime_paths", return_value=runtime_paths), mock.patch.object(
                monitor_log,
                "log_file_candidates",
                return_value=[expected],
            ):
                monitor_log._write_logmon_state(
                    active=True,
                    tailing_file=None,
                    watching_server=True,
                    status="waiting_for_log",
                    message=f"Waiting for game log: {expected}",
                    server_joinable=True,
                )

            payload = json.loads(state.read_text(encoding="utf-8"))

        self.assertTrue(payload["active"])
        self.assertEqual(payload["status"], "waiting_for_log")
        self.assertEqual(payload["expected_log_files"], [str(expected)])
        self.assertIn(str(expected), payload["message"])
        self.assertTrue(payload["server_joinable"])

    def test_disconnect_uses_cached_player_name_and_marks_player_offline(self) -> None:
        steam_id = "76561198000000001"
        monitor_log._remember_identity(steam_id, "Example Player")
        monitor_log._record_player_event(
            steam_id,
            "join",
            source="log",
            name="Example Player",
            state="online",
        )
        line = (
            "[2026.07.24-15.50.53:405][120]LogNet: "
            "UNetDriver::RemoveClientConnection - Removed address "
            f"{steam_id}:0 from MappedClientConnections for: [UNetConnection]"
        )

        message = monitor_log._disconnect_message_for_line(line, observed_at=100.0)

        self.assertEqual(message, "👋 **Example Player** disconnected.")
        self.assertEqual(
            monitor_log._PLAYER_CACHE[steam_id]["online_state"], "offline"
        )
        self.assertEqual(
            monitor_log._PLAYER_CACHE[steam_id]["events"][-1]["type"],
            "disconnect",
        )

    def test_log_output_device_lines_never_match_disconnect(self) -> None:
        line = (
            "[2026.07.24-15.49.48:629][178]LogOutputDevice: Verbose: "
            "[Callstack] VeinServer-Win64-Test.exe!GuardedMain()"
        )

        message = monitor_log._disconnect_message_for_line(line, observed_at=100.0)

        self.assertIsNone(message)
        self.assertEqual(monitor_log._PLAYER_CACHE, {})
        self.assertEqual(monitor_log._LAST_DISCONNECT_NOTIFY, {})

    def test_repeated_disconnect_for_same_player_is_debounced(self) -> None:
        steam_id = "76561198000000002"
        line = (
            "LogNet: UNetDriver::RemoveClientConnection - Removed address "
            f"{steam_id}:0 from MappedClientConnections for: [UNetConnection]"
        )

        first = monitor_log._disconnect_message_for_line(line, observed_at=100.0)
        repeated = monitor_log._disconnect_message_for_line(line, observed_at=110.0)

        self.assertEqual(first, f"👋 Steam ID `{steam_id}` disconnected.")
        self.assertIsNone(repeated)
        self.assertEqual(len(monitor_log._PLAYER_CACHE[steam_id]["events"]), 1)

    def test_player_event_redacts_login_credentials_before_snapshot(self) -> None:
        steam_id = "76561198000000003"
        raw_line = (
            "LogNet: Login request: ?Password=private-value?Name=Example Player"
            f"??ID={steam_id}?Ticket=session-value?SplitscreenCount=1"
        )

        monitor_log._record_player_event(
            steam_id,
            "login_request",
            source="log",
            name="Example Player",
            raw_line=raw_line,
            state="connecting",
        )
        payload = monitor_log._player_snapshot_from_cache()
        stored_line = payload["players"][0]["events"][0]["line"]

        self.assertNotIn("private-value", stored_line)
        self.assertNotIn("session-value", stored_line)
        self.assertIn("?Password=<redacted>", stored_line)
        self.assertIn("?Ticket=<redacted>", stored_line)
        self.assertIn("?Name=Example Player", stored_line)

    def test_player_event_preserves_non_sensitive_diagnostic_line(self) -> None:
        line = "LogNet: Join succeeded: Example Player"

        self.assertEqual(monitor_log._redact_player_event_line(line), line)

    def test_existing_snapshot_is_redacted_on_monitor_startup_migration(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            snapshot = Path(tmp) / "player_characters.json"
            snapshot.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "players": [
                            {
                                "name": "Example Player",
                                "events": [
                                    {
                                        "type": "login_request",
                                        "line": (
                                            "?Password=private-value?Name=Example"
                                            "?Ticket=session-value"
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(monitor_log, "PLAYER_SNAPSHOT_FILE", snapshot):
                changed = monitor_log._redact_existing_player_snapshot()
            payload = json.loads(snapshot.read_text(encoding="utf-8"))

        stored_line = payload["players"][0]["events"][0]["line"]
        self.assertTrue(changed)
        self.assertNotIn("private-value", stored_line)
        self.assertNotIn("session-value", stored_line)
        self.assertEqual(
            stored_line,
            "?Password=<redacted>?Name=Example?Ticket=<redacted>",
        )

    def test_unreadable_existing_snapshot_is_left_untouched(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            snapshot = Path(tmp) / "player_characters.json"
            snapshot.write_text("not-json", encoding="utf-8")
            with mock.patch.object(monitor_log, "PLAYER_SNAPSHOT_FILE", snapshot):
                changed = monitor_log._redact_existing_player_snapshot()

            self.assertFalse(changed)
            self.assertEqual(snapshot.read_text(encoding="utf-8"), "not-json")

    def test_sanitized_real_session_fixture_classifies_only_expected_events(self) -> None:
        rows = SANITIZED_LOG_FIXTURE.read_text(encoding="utf-8").splitlines()

        for row in rows:
            if not row or row.startswith("#"):
                continue
            expected_text, line = row.split("\t", 1)
            expected = set() if expected_text == "none" else set(expected_text.split(","))
            with self.subTest(line=line):
                self.assertEqual(monitor_log._classify_log_line(line), expected)

    def test_initial_attach_skips_old_history_but_reads_new_appended_lines(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_path = Path(tmp) / "Vein.log"
            old_line = "LogWorld: Bringing World Old.World up for play\n"
            log_path.write_text(old_line, encoding="utf-8")
            initial = monitor_log._log_file_signature(log_path)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("LogWorld: Bringing World New.World up for play\n")

            position = monitor_log._initial_attach_position(log_path, initial)
            with log_path.open("rb") as handle:
                handle.seek(position)
                remaining = handle.read().decode("utf-8")

        self.assertIsNotNone(initial)
        self.assertEqual(position, initial[2])
        self.assertNotIn("Old.World", remaining)
        self.assertIn("New.World", remaining)

    def test_initial_attach_reads_replaced_or_truncated_log_from_start(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_path = Path(tmp) / "Vein.log"
            log_path.write_text("old history that is longer\n", encoding="utf-8")
            initial = monitor_log._log_file_signature(log_path)
            log_path.write_text("new\n", encoding="utf-8")

            position = monitor_log._initial_attach_position(log_path, initial)

        self.assertEqual(position, 0)

    def test_initial_attach_reads_newly_created_log_from_start(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            log_path = Path(tmp) / "Vein.log"
            log_path.write_text("new launch\n", encoding="utf-8")

            position = monitor_log._initial_attach_position(log_path, None)

        self.assertEqual(position, 0)


if __name__ == "__main__":
    unittest.main()
