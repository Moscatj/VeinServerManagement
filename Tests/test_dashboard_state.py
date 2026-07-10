from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from GUI.dashboard_state import normalize_player_snapshot, server_runtime_labels  # noqa: E402


class DashboardStateTests(unittest.TestCase):
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
