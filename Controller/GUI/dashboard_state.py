"""Pure presentation-state helpers for the monitoring dashboard."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def home_health_state(
    *,
    server_available: bool,
    server_running: bool,
    log_monitor_running: bool,
    log_monitor_fresh: bool,
    crash_monitor_running: bool,
    backups_enabled: bool,
) -> dict[str, Any]:
    """Build concise Home status and guidance without performing any actions."""
    server = {
        "text": "Running" if server_running else "Stopped" if server_available else "Setup required",
        "state": "healthy" if server_running else "neutral" if server_available else "warning",
    }
    log_monitor = {
        "text": (
            "Running"
            if log_monitor_running and log_monitor_fresh
            else "Stale"
            if log_monitor_running
            else "Stopped"
        ),
        "state": (
            "healthy"
            if log_monitor_running and log_monitor_fresh
            else "warning"
            if server_running
            else "neutral"
        ),
    }
    crash_monitor = {
        "text": "Running" if crash_monitor_running else "Stopped",
        "state": "healthy" if crash_monitor_running else "warning" if server_running else "neutral",
    }
    backups = {
        "text": "Enabled" if backups_enabled else "Disabled",
        "state": "healthy" if backups_enabled else "warning",
    }

    if not server_available and not server_running:
        guidance = {
            "kind": "warning",
            "text": "No Vein server is selected. Open Setup to install or select one.",
        }
    elif not server_running:
        guidance = {
            "kind": "info",
            "text": "The server is ready but stopped. Use Start Server above when you are ready.",
        }
    else:
        issues = []
        if not log_monitor_running:
            issues.append("log monitoring is stopped")
        elif not log_monitor_fresh:
            issues.append("log monitoring is stale")
        if not crash_monitor_running:
            issues.append("crash monitoring is stopped")
        if not backups_enabled:
            issues.append("backups are disabled")
        guidance = (
            {
                "kind": "warning",
                "text": "Server is running, but " + ", ".join(issues) + ". Review safeguards below.",
            }
            if issues
            else {
                "kind": "success",
                "text": "Server is running and its configured safeguards are active.",
            }
        )

    return {
        "server": server,
        "log_monitor": log_monitor,
        "crash_monitor": crash_monitor,
        "backups": backups,
        "guidance": guidance,
    }


def startup_runtime_feedback(
    *,
    server_running: bool,
    server_joinable: bool,
    log_monitor_running: bool,
    crash_monitor_running: bool,
) -> dict[str, Any] | None:
    """Describe an observable startup milestone without guessing subprocess work."""
    if server_running and server_joinable:
        return {
            "step": 5,
            "state": "complete",
            "text": "Server is ready and joinable.",
        }
    if server_running:
        return {
            "step": 4,
            "state": "active",
            "text": "Server process started; waiting for the game server to become joinable.",
        }
    if log_monitor_running or crash_monitor_running:
        names = []
        if log_monitor_running:
            names.append("log")
        if crash_monitor_running:
            names.append("crash")
        return {
            "step": 3,
            "state": "active",
            "text": f"Starting safeguards: {', '.join(names)} monitor active.",
        }
    return None


def runtime_server_joinable(
    server_state: Mapping[str, Any] | None,
    log_monitor_state: Mapping[str, Any] | None,
) -> bool:
    """Prefer the log monitor's observed readiness over legacy server state."""
    for source in (log_monitor_state, server_state):
        if not isinstance(source, Mapping) or "server_joinable" not in source:
            continue
        value = source.get("server_joinable")
        return value is True or str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "joinable",
            "ready",
        }
    return False


def should_autostart_log_monitor(
    *,
    server_running: bool,
    monitor_enabled: bool,
    monitor_running: bool,
    manual_stop: bool,
    lifecycle_busy: bool,
    shutdown_in_progress: bool,
) -> bool:
    """Prevent monitor recovery from racing an intentional lifecycle action."""
    return (
        server_running
        and monitor_enabled
        and not monitor_running
        and not manual_stop
        and not lifecycle_busy
        and not shutdown_in_progress
    )


def server_action_state(
    server_available: bool, server_running: bool
) -> dict[str, Any]:
    """Return explicit server state and safe action availability for the shell."""
    if server_running:
        return {
            "label": "Running",
            "primary_action": "stop",
            "primary_label": "Stop Server",
            "primary_role": "danger",
            "can_start": False,
            "can_stop": True,
            "can_restart": server_available,
            "needs_setup": False,
        }
    if not server_available:
        return {
            "label": "Setup required",
            "primary_action": "setup",
            "primary_label": "Set Up Server…",
            "primary_role": "primary",
            "can_start": False,
            "can_stop": False,
            "can_restart": False,
            "needs_setup": True,
        }
    return {
        "label": "Stopped",
        "primary_action": "start",
        "primary_label": "Start Server",
        "primary_role": "primary",
        "can_start": True,
        "can_stop": False,
        "can_restart": False,
        "needs_setup": False,
    }


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
