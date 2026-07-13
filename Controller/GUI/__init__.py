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
from .dashboard_state import normalize_player_snapshot, server_runtime_labels
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
from .design_system import (
    InlineNotice,
    PageHeader,
    StatusBadge,
    apply_design_system,
    set_button_role,
)
from .kvrow import KVRow
from .player_details import handle_player_tree_double_click, show_json_dialog
from .status import StatusBus, StatusPoller
from .preflight import PreflightWorker, summarize_preflight
from .server_config_view import (
    ServerConfigEditWorker,
    ServerConfigPreviewWorker,
    build_server_config_preview_view,
    edit_values_from_text,
)
from .quickstart import (
    ExistingServerLoadWorker,
    apply_quick_start,
    build_quick_start_preview,
    build_quick_start_view,
    collect_quick_start_values,
    enforce_quick_start_root_mode,
    format_quick_start_plan,
    populate_existing_server_settings,
    quick_start_config_path,
    set_quick_start_mode,
    update_quick_start_game_log_path,
    update_quick_start_save_games_path,
)
from .about import about_text, show_about_dialog

__all__ = [
    "NavigationItem",
    "NavigationPanel",
    "build_config_editor",
    "ConfigRenderer",
    "build_dashboard",
    "normalize_player_snapshot",
    "server_runtime_labels",
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
    "InlineNotice",
    "PageHeader",
    "StatusBadge",
    "apply_design_system",
    "set_button_role",
    "KVRow",
    "handle_player_tree_double_click",
    "show_json_dialog",
    "StatusBus",
    "StatusPoller",
    "PreflightWorker",
    "summarize_preflight",
    "ServerConfigPreviewWorker",
    "ServerConfigEditWorker",
    "build_server_config_preview_view",
    "edit_values_from_text",
    "build_quick_start_view",
    "build_quick_start_preview",
    "ExistingServerLoadWorker",
    "apply_quick_start",
    "collect_quick_start_values",
    "enforce_quick_start_root_mode",
    "format_quick_start_plan",
    "populate_existing_server_settings",
    "quick_start_config_path",
    "set_quick_start_mode",
    "update_quick_start_game_log_path",
    "update_quick_start_save_games_path",
    "about_text",
    "show_about_dialog",
]
