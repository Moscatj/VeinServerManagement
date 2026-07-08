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
    build_placeholder_view,
)
from .logs import (
    LogPanelController,
    FileTail,
    LogSearchWorker,
    LogErrorWorker,
    ArchiveLogsWorker,
)
from .process_control import ProcessController
from .status_view import StatusRenderer
from .nav_control import NavigationController
from .config_controller import ConfigController
from .panels import build_log_panel
from .widgets import CollapsibleBox
from .kvrow import KVRow
from .player_details import handle_player_tree_double_click, show_json_dialog
from .status import StatusBus, StatusPoller
from .preflight import PreflightWorker, summarize_preflight
from .server_config_view import (
    ServerConfigPreviewWorker,
    build_server_config_preview_view,
)
from .about import about_text, show_about_dialog

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
    "ProcessController",
    "StatusRenderer",
    "NavigationController",
    "ConfigController",
    "LogPanelController",
    "FileTail",
    "LogSearchWorker",
    "LogErrorWorker",
    "ArchiveLogsWorker",
    "CollapsibleBox",
    "KVRow",
    "handle_player_tree_double_click",
    "show_json_dialog",
    "StatusBus",
    "StatusPoller",
    "PreflightWorker",
    "summarize_preflight",
    "ServerConfigPreviewWorker",
    "build_server_config_preview_view",
    "about_text",
    "show_about_dialog",
]
