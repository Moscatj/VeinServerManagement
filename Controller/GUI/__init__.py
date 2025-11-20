"""
Helper widgets for the Vein Manager GUI.

This package will gradually host split-out UI components so the main
vein_manager.py entrypoint can stay small and focused on orchestration.
"""

from __future__ import annotations

from .navigation import NavigationItem, NavigationPanel
from .config_editor import build_config_editor
from .config_renderer import ConfigRenderer
from .dashboard import build_dashboard
from .panels import (
    build_command_bar,
    build_left_panel,
    build_log_panel,
    build_placeholder_view,
)
from .widgets import CollapsibleBox
from .kvrow import KVRow
from .player_details import handle_player_tree_double_click, show_json_dialog
from .status import StatusBus, StatusPoller

__all__ = [
    "NavigationItem",
    "NavigationPanel",
    "build_config_editor",
    "ConfigRenderer",
    "build_dashboard",
    "build_command_bar",
    "build_left_panel",
    "build_log_panel",
    "build_placeholder_view",
    "CollapsibleBox",
    "KVRow",
    "handle_player_tree_double_click",
    "show_json_dialog",
    "StatusBus",
    "StatusPoller",
]
