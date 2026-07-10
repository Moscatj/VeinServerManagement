"""Pure presentation-state helpers for the monitoring dashboard."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def server_runtime_labels(server_online: bool, state: Mapping[str, Any] | None) -> dict[str, str]:
    """Return truthful runtime labels, treating process state as authoritative."""
    if not server_online:
        return {
            "joinable": "Joinable: no (server offline)",
            "players": "Players: 0 (server offline)",
            "uptime": "Uptime: - (server offline)",
        }

    data = state or {}
    uptime = data.get("uptime_seconds")
    uptime_text = "Uptime: -"
    if isinstance(uptime, int):
        uptime_text = f"Uptime: {uptime // 3600:02d}:{(uptime % 3600) // 60:02d}:{uptime % 60:02d}"
    return {
        "joinable": f"Joinable: {data.get('server_joinable', '-')}",
        "players": f"Players: {data.get('player_count', '-')}",
        "uptime": uptime_text,
    }


def normalize_player_snapshot(snapshot: Mapping[str, Any] | None, server_online: bool) -> dict[str, Any]:
    """Prevent persisted snapshots from reporting online users after shutdown."""
    data = deepcopy(dict(snapshot or {}))
    if server_online:
        return data

    data["admins"] = []
    players = data.get("players")
    if isinstance(players, list):
        for player in players:
            if not isinstance(player, dict):
                continue
            player["online"] = False
            player["online_state"] = "offline"
            player["in_character_select"] = False
            player["status"] = "offline"
    return data
