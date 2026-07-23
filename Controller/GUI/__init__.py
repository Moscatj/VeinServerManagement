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
from .dashboard_state import (
    home_health_state,
    normalize_player_snapshot,
    server_action_state,
    runtime_server_joinable,
    server_runtime_labels,
    should_autostart_log_monitor,
    startup_runtime_feedback,
)
from .panels import (
    build_command_bar,
    build_left_panel,
    set_startup_feedback,
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
    IdentityAccessEditWorker,
    ServerConfigEditWorker,
    ServerConfigPreviewWorker,
    build_identity_access_edits,
    build_server_config_preview_view,
    collect_identity_access_values,
    edit_values_from_text,
    identity_access_change_summary,
    identity_access_values_from_preview,
    mask_sensitive_config_diff,
    populate_identity_access_form,
    summarize_server_config_validation,
    validate_identity_access_values,
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
    route_quick_start_workflow,
    set_quick_start_step,
    set_quick_start_mode,
    update_quick_start_game_log_path,
    update_quick_start_save_games_path,
)
from .about import about_text, show_about_dialog
from .backup_view import (
    BackupHistoryWorker,
    BackupPolicyWorker,
    RestorePointWorker,
    RestorePreviewWorker,
    apply_backup_history_filter,
    backup_history_summary,
    build_backup_history_view,
    build_restore_preview_dialog,
    collect_backup_policy,
    filter_backup_archives,
    format_archive_size,
    populate_backup_policy,
    populate_backup_history,
    prompt_restore_point_details,
)

__all__ = [
    "NavigationItem",
    "NavigationPanel",
    "build_config_editor",
    "ConfigRenderer",
    "build_dashboard",
    "home_health_state",
    "normalize_player_snapshot",
    "server_action_state",
    "runtime_server_joinable",
    "server_runtime_labels",
    "should_autostart_log_monitor",
    "startup_runtime_feedback",
    "build_command_bar",
    "build_left_panel",
    "set_startup_feedback",
    "build_log_panel",
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
    "IdentityAccessEditWorker",
    "build_server_config_preview_view",
    "build_identity_access_edits",
    "collect_identity_access_values",
    "edit_values_from_text",
    "identity_access_change_summary",
    "identity_access_values_from_preview",
    "mask_sensitive_config_diff",
    "populate_identity_access_form",
    "summarize_server_config_validation",
    "validate_identity_access_values",
    "build_quick_start_view",
    "build_quick_start_preview",
    "ExistingServerLoadWorker",
    "apply_quick_start",
    "collect_quick_start_values",
    "enforce_quick_start_root_mode",
    "format_quick_start_plan",
    "populate_existing_server_settings",
    "quick_start_config_path",
    "route_quick_start_workflow",
    "set_quick_start_step",
    "set_quick_start_mode",
    "update_quick_start_game_log_path",
    "update_quick_start_save_games_path",
    "about_text",
    "show_about_dialog",
    "BackupHistoryWorker",
    "BackupPolicyWorker",
    "RestorePointWorker",
    "RestorePreviewWorker",
    "apply_backup_history_filter",
    "backup_history_summary",
    "build_backup_history_view",
    "build_restore_preview_dialog",
    "collect_backup_policy",
    "filter_backup_archives",
    "format_archive_size",
    "populate_backup_policy",
    "populate_backup_history",
    "prompt_restore_point_details",
]
