from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from GUI.dashboard_state import (  # noqa: E402
    home_health_state,
    normalize_player_snapshot,
    runtime_server_joinable,
    server_action_state,
    server_runtime_labels,
    should_autostart_log_monitor,
    startup_runtime_feedback,
)


class DashboardStateTests(unittest.TestCase):
    def test_log_monitor_autostart_is_suppressed_during_shutdown(self) -> None:
        base = {
            "server_running": True,
            "monitor_enabled": True,
            "monitor_running": False,
            "manual_stop": False,
            "lifecycle_busy": False,
            "shutdown_in_progress": False,
        }
        self.assertTrue(should_autostart_log_monitor(**base))
        self.assertFalse(
            should_autostart_log_monitor(**{**base, "lifecycle_busy": True})
        )
        self.assertFalse(
            should_autostart_log_monitor(
                **{**base, "shutdown_in_progress": True}
            )
        )

    def test_runtime_joinable_prefers_log_monitor_observation(self) -> None:
        self.assertTrue(
            runtime_server_joinable(
                {"server_joinable": False},
                {"server_joinable": True},
            )
        )
        self.assertTrue(runtime_server_joinable({}, {"server_joinable": "ready"}))
        self.assertFalse(runtime_server_joinable({"status": "running"}, {}))

    def test_startup_runtime_feedback_advances_from_monitors_to_ready(self) -> None:
        self.assertIsNone(
            startup_runtime_feedback(
                server_running=False,
                server_joinable=False,
                log_monitor_running=False,
                crash_monitor_running=False,
            )
        )
        monitors = startup_runtime_feedback(
            server_running=False,
            server_joinable=False,
            log_monitor_running=True,
            crash_monitor_running=True,
        )
        waiting = startup_runtime_feedback(
            server_running=True,
            server_joinable=False,
            log_monitor_running=True,
            crash_monitor_running=True,
        )
        ready = startup_runtime_feedback(
            server_running=True,
            server_joinable=True,
            log_monitor_running=True,
            crash_monitor_running=True,
        )

        self.assertEqual(monitors["step"], 3)
        self.assertIn("log, crash", monitors["text"])
        self.assertEqual(waiting["step"], 4)
        self.assertIn("joinable", waiting["text"])
        self.assertEqual(ready["state"], "complete")
        self.assertEqual(ready["step"], 5)

    def test_home_health_state_prioritizes_setup_and_running_warnings(self) -> None:
        setup = home_health_state(
            server_available=False,
            server_running=False,
            log_monitor_running=False,
            log_monitor_fresh=False,
            crash_monitor_running=False,
            backups_enabled=True,
        )
        warning = home_health_state(
            server_available=True,
            server_running=True,
            log_monitor_running=True,
            log_monitor_fresh=False,
            crash_monitor_running=False,
            backups_enabled=False,
        )

        self.assertEqual(setup["server"]["text"], "Setup required")
        self.assertEqual(setup["guidance"]["kind"], "warning")
        self.assertIn("Open Setup", setup["guidance"]["text"])
        self.assertEqual(warning["server"]["state"], "healthy")
        self.assertEqual(warning["log_monitor"]["text"], "Stale")
        self.assertEqual(warning["crash_monitor"]["state"], "warning")
        self.assertEqual(warning["backups"]["text"], "Disabled")
        self.assertIn("safeguards", warning["guidance"]["text"])

    def test_home_health_state_reports_healthy_running_server(self) -> None:
        health = home_health_state(
            server_available=True,
            server_running=True,
            log_monitor_running=True,
            log_monitor_fresh=True,
            crash_monitor_running=True,
            backups_enabled=True,
        )

        self.assertEqual(health["guidance"]["kind"], "success")
        self.assertEqual(health["log_monitor"]["state"], "healthy")

    def test_server_action_state_is_explicit_and_safe(self) -> None:
        setup = server_action_state(False, False)
        stopped = server_action_state(True, False)
        running = server_action_state(True, True)
        running_without_files = server_action_state(False, True)

        self.assertEqual(setup["label"], "Setup required")
        self.assertEqual(setup["primary_action"], "setup")
        self.assertEqual(setup["primary_label"], "Set Up Server…")
        self.assertTrue(setup["needs_setup"])
        self.assertFalse(setup["can_start"])
        self.assertEqual(stopped["label"], "Stopped")
        self.assertEqual(stopped["primary_action"], "start")
        self.assertEqual(stopped["primary_role"], "primary")
        self.assertTrue(stopped["can_start"])
        self.assertFalse(stopped["can_stop"])
        self.assertEqual(running["label"], "Running")
        self.assertEqual(running["primary_action"], "stop")
        self.assertEqual(running["primary_label"], "Stop Server")
        self.assertEqual(running["primary_role"], "danger")
        self.assertTrue(running["can_stop"])
        self.assertTrue(running["can_restart"])
        self.assertEqual(running_without_files["primary_action"], "stop")
        self.assertTrue(running_without_files["can_stop"])
        self.assertFalse(running_without_files["can_restart"])

    def test_offline_server_overrides_persisted_runtime_counts(self) -> None:
        labels = server_runtime_labels(
            False,
            {"server_joinable": True, "player_count": 3, "uptime_seconds": 3600},
        )

        self.assertEqual(labels["joinable"], "Joinable: no (server offline)")
        self.assertEqual(labels["players"], "Players: 0 (server offline)")
        self.assertEqual(labels["uptime"], "Uptime: - (server offline)")

    def test_online_server_uses_current_runtime_values(self) -> None:
        labels = server_runtime_labels(
            True,
            {"server_joinable": True, "player_count": 2, "uptime_seconds": 3661},
        )

        self.assertEqual(labels["joinable"], "Joinable: True")
        self.assertEqual(labels["players"], "Players: 2")
        self.assertEqual(labels["uptime"], "Uptime: 01:01:01")

    def test_offline_server_marks_snapshot_players_offline_without_mutating_source(self) -> None:
        source = {
            "admins": [{"steam_id": "111", "name": "Admin"}],
            "players": [
                {
                    "steam_id": "111",
                    "name": "Admin",
                    "online": True,
                    "online_state": "playing",
                    "in_character_select": True,
                }
            ],
        }

        normalized = normalize_player_snapshot(source, False)

        self.assertEqual(normalized["admins"], [])
        self.assertFalse(normalized["players"][0]["online"])
        self.assertEqual(normalized["players"][0]["online_state"], "offline")
        self.assertFalse(normalized["players"][0]["in_character_select"])
        self.assertTrue(source["players"][0]["online"])

    def test_online_snapshot_is_copied_without_forcing_state(self) -> None:
        source = {"players": [{"steam_id": "111", "online": True}]}

        normalized = normalize_player_snapshot(source, True)

        self.assertTrue(normalized["players"][0]["online"])
        self.assertIsNot(normalized, source)


if __name__ == "__main__":
    unittest.main()
