from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from PySide6 import QtCore, QtWidgets  # noqa: E402

from GUI.kvrow import KVRow  # noqa: E402
from GUI.navigation import NavigationItem, NavigationPanel  # noqa: E402
from GUI.about import about_text  # noqa: E402
from GUI.player_details import populate_json_tree  # noqa: E402
from GUI.quickstart import (  # noqa: E402
    build_quick_start_preview,
    build_quick_start_view,
    collect_quick_start_values,
    enforce_quick_start_root_mode,
    populate_existing_server_settings,
    quick_start_config_path,
    route_quick_start_workflow,
    set_quick_start_step,
    set_quick_start_password_visibility,
    set_quick_start_webhook_visibility,
    set_quick_start_mode,
)
from Tools.server_quickstart import ExistingServerSettings, ServerRootInspection  # noqa: E402
from Tools.setup_state import (  # noqa: E402
    SetupAssessment,
    SetupMetadata,
    SetupState,
    SetupWorkflow,
)
from GUI.server_config_view import (  # noqa: E402
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
from GUI.status_view import StatusRenderer  # noqa: E402
from GUI.widgets import CollapsibleBox  # noqa: E402
from GUI.backup_view import (  # noqa: E402
    backup_retention_explanation,
    build_backup_history_view,
    collect_backup_policy,
    format_archive_size,
    populate_backup_policy,
    populate_backup_history,
    review_backup_policy,
)
from Tools.backup_policy import BackupPolicy  # noqa: E402
from GUI.design_system import (  # noqa: E402
    BUTTON_DANGER,
    BUTTON_PRIMARY,
    InlineNotice,
    PageHeader,
    StatusBadge,
    application_stylesheet,
    set_button_role,
)
from GUI.dashboard import build_dashboard  # noqa: E402
from GUI.panels import build_command_bar, set_startup_feedback  # noqa: E402


def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class GuiHelperTests(unittest.TestCase):
    def test_backup_policy_form_tracks_reviews_and_discards_changes(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_backup_history_view(owner)
        baseline = BackupPolicy(
            enabled=True,
            on_autosave=False,
            on_crash_detect=True,
            on_shutdown=True,
            max_backups=10,
            max_age_days=7,
        )
        populate_backup_policy(owner, baseline)

        self.assertEqual(collect_backup_policy(owner), baseline)
        self.assertEqual(owner.grpBackupPolicyTriggers.title(), "Automatic backups")
        self.assertIn("more than 7 full days old", owner.lblBackupPolicyRetentionHelp.text())
        self.assertIn("does not immediately delete", owner.lblBackupPolicyRetentionHelp.text())
        self.assertTrue(owner.wdgBackupPolicyOptions.isEnabled())
        self.assertFalse(owner.btnBackupPolicyReview.isEnabled())
        owner.chkBackupPolicyAutosave.setChecked(True)
        owner.spinBackupPolicyCount.setValue(25)
        self.assertIn("keep at most 25", owner.lblBackupPolicyRetentionHelp.text())
        self.assertTrue(owner.btnBackupPolicyReview.isEnabled())
        self.assertFalse(owner.btnBackupPolicyApply.isEnabled())

        review_backup_policy(owner)
        self.assertTrue(owner.btnBackupPolicyApply.isEnabled())
        self.assertIn("Autosave", owner.lblBackupPolicyReview.text())
        self.assertIn("25 archive(s)", owner.lblBackupPolicyReview.text())

        owner.btnBackupPolicyDiscard.click()
        self.assertEqual(collect_backup_policy(owner), baseline)
        self.assertFalse(owner.btnBackupPolicyReview.isEnabled())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_backup_policy_master_switch_disables_subordinate_controls(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_backup_history_view(owner)
        populate_backup_policy(owner, BackupPolicy(enabled=True))

        owner.chkBackupPolicyEnabled.setChecked(False)

        self.assertFalse(owner.wdgBackupPolicyOptions.isEnabled())
        self.assertFalse(owner.chkBackupPolicyAutosave.isEnabled())
        self.assertFalse(owner.btnBackupHistoryCreate.isEnabled())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_backup_cleanup_switches_control_each_limit(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_backup_history_view(owner)
        populate_backup_policy(owner, BackupPolicy())

        owner.chkBackupPolicyCleanupCount.setChecked(False)
        self.assertFalse(owner.spinBackupPolicyCount.isEnabled())
        self.assertTrue(owner.spinBackupPolicyAge.isEnabled())
        self.assertNotIn("keep at most", owner.lblBackupPolicyRetentionHelp.text())
        owner.chkBackupPolicyCleanupEnabled.setChecked(False)
        self.assertFalse(owner.wdgBackupPolicyCleanupOptions.isEnabled())
        self.assertIn("cleanup is off", owner.lblBackupPolicyRetentionHelp.text())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_backup_retention_explanation_uses_plain_language(self) -> None:
        text = backup_retention_explanation(
            BackupPolicy(max_backups=12, max_age_days=30)
        )

        self.assertIn("keep at most 12 archives per backup type", text)
        self.assertIn("more than 30 full days old", text)
        self.assertIn("does not immediately delete", text)

    def test_backup_history_view_renders_read_only_archive_metadata(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_backup_history_view(owner)
        populate_backup_history(
            owner,
            {
                "ok": True,
                "root": "C:/Backups",
                "error": "",
                "archives": [
                    {
                        "modified": "2026-07-23T12:00:00-04:00",
                        "category": "Manual",
                        "filename": "Server_Manual.zip",
                        "size_bytes": 1536,
                        "path": "C:/Backups/Manual/Server_Manual.zip",
                    }
                ],
            },
        )

        self.assertIsInstance(widget, QtWidgets.QWidget)
        self.assertEqual(owner.treeBackupHistory.columnCount(), 4)
        self.assertEqual(owner.treeBackupHistory.topLevelItemCount(), 1)
        self.assertEqual(owner.treeBackupHistory.topLevelItem(0).text(3), "1.5 KB")
        self.assertIn("Showing 1 newest", owner.lblBackupHistoryStatus.text())
        self.assertEqual(owner.btnBackupHistoryCreate.text(), "Backup Now")
        self.assertEqual(format_archive_size(0), "0 B")
        self.assertEqual(format_archive_size(1024 * 1024), "1.0 MB")

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = app()

    def test_kvrow_values_and_set_value(self) -> None:
        bool_row = KVRow("Enabled", ("features", "enabled"), True)
        text_row = KVRow("Path", ("paths", "server_dir"), "C:/Server")

        self.assertTrue(bool_row.value())
        bool_row.set_value(False)
        self.assertFalse(bool_row.value())
        self.assertEqual(text_row.value(), "C:/Server")
        text_row.set_value("D:/Server")
        self.assertEqual(text_row.value(), "D:/Server")
        browse_btn = text_row.findChild(QtWidgets.QToolButton)
        self.assertIsNotNone(browse_btn)
        self.assertEqual(browse_btn.text(), "...")

    def test_collapsible_box_count_and_toggle(self) -> None:
        box = CollapsibleBox("Section")
        box.show()
        box.set_count(3, active=True)

        self.assertEqual(box.toggle.text(), "Section  (3)")
        box.toggle.setChecked(False)
        self.assertFalse(box.container.isVisible())
        self.assertEqual(box.toggle.arrowType(), QtCore.Qt.RightArrow)

    def test_design_system_components_expose_semantic_state(self) -> None:
        header = PageHeader("Home", "Server overview")
        notice = InlineNotice("Check configuration", "warning")
        badge = StatusBadge("Stopped")
        button = QtWidgets.QPushButton("Start")

        set_button_role(button, BUTTON_PRIMARY)
        badge.set_state("healthy", "Running")

        self.assertEqual(header.title_label.text(), "Home")
        self.assertEqual(header.subtitle_label.text(), "Server overview")
        self.assertEqual(notice.property("noticeKind"), "warning")
        self.assertEqual(badge.property("statusState"), "healthy")
        self.assertEqual(badge.text(), "Running")
        self.assertEqual(button.property("buttonRole"), BUTTON_PRIMARY)

    def test_design_system_stylesheet_targets_roles_without_global_colors(self) -> None:
        css = application_stylesheet()

        self.assertIn('buttonRole="primary"', css)
        self.assertIn('buttonRole="danger"', css)
        self.assertIn('noticeKind="error"', css)
        self.assertIn('statusState="healthy"', css)
        self.assertIn('pageSubtitle="true"] { color: palette(text)', css)
        self.assertIn('fieldHelp="true"] { color: palette(text)', css)
        self.assertIn("background: palette(base);", css)
        self.assertIn("background: palette(window);", css)
        self.assertNotIn('pageSubtitle="true"] { color: palette(mid)', css)
        self.assertNotIn('fieldHelp="true"] { color: palette(mid)', css)

        button = QtWidgets.QPushButton("Stop")
        set_button_role(button, BUTTON_DANGER)
        self.assertEqual(button.property("buttonRole"), BUTTON_DANGER)

    def test_dashboard_uses_scrollable_minimum_size_content(self) -> None:
        class Owner:
            pass

        owner = Owner()
        dashboard = build_dashboard(owner, lambda *_: "")
        content = owner.dashboardScroll.widget()

        self.assertIsInstance(dashboard, QtWidgets.QWidget)
        self.assertTrue(owner.dashboardScroll.widgetResizable())
        self.assertEqual(owner.dashboardScroll.frameShape(), QtWidgets.QFrame.NoFrame)
        self.assertEqual(content.objectName(), "dashboardContent")
        self.assertEqual(content.layout().sizeConstraint(), QtWidgets.QLayout.SetMinimumSize)
        self.assertEqual(owner.badgeHomeServer.text(), "Checking")
        self.assertEqual(owner.badgeHomeLogMonitor.text(), "Checking")
        self.assertEqual(owner.badgeHomeCrashMonitor.text(), "Checking")
        self.assertEqual(owner.badgeHomeBackups.text(), "Checking")
        self.assertEqual(owner.btnHomeSetup.text(), "Open Setup")
        self.assertEqual(owner.btnHomeLogs.text(), "View Logs")
        self.assertEqual(owner.btnBkNow.text(), "Backup Now")
        self.assertEqual(owner.btnBkView.text(), "View Backups")
        self.assertFalse(hasattr(owner, "lblBkFile"))
        self.assertFalse(hasattr(owner, "lblBkCounts"))
        self.assertTrue(owner.noticeHomeGuidance.wordWrap())

        class Navigation:
            selected = None

            def set_default_selection(self, view_id: str) -> None:
                self.selected = view_id

        owner.nav_panel = Navigation()
        owner.btnHomeSetup.click()
        self.assertEqual(owner.nav_panel.selected, "monitor.quick_start")
        owner.btnHomeLogs.click()
        self.assertEqual(owner.nav_panel.selected, "monitor.logs")
        owner.btnBkView.click()
        self.assertEqual(owner.nav_panel.selected, "monitor.backups")

    def test_command_bar_reserves_readable_status_width(self) -> None:
        class Owner:
            pass

        owner = Owner()
        bar = build_command_bar(owner, lambda *_: "")

        self.assertIsInstance(bar, QtWidgets.QWidget)
        self.assertGreaterEqual(owner.status_label.minimumWidth(), 260)
        self.assertTrue(owner.status_label.wordWrap())
        self.assertEqual(owner.lbl_server_state.text(), "Checking…")
        self.assertGreaterEqual(owner.lbl_server_state.minimumWidth(), 92)
        self.assertEqual(owner.b_server_action.text(), "Checking…")
        self.assertEqual(owner.b_server_action.property("serverAction"), "checking")
        self.assertEqual(owner.b_monitors.text(), "Monitors…")
        self.assertEqual(len(owner.monitor_menu.actions()), 5)
        self.assertEqual(owner.a_lm_on.text(), "Start Log Monitor")
        self.assertEqual(owner.a_cm_off.text(), "Stop Crash Monitor")
        self.assertFalse(owner.startup_feedback_panel.isVisible())

        set_startup_feedback(
            owner,
            "Server process started; waiting for joinable.",
            step=4,
        )
        self.assertFalse(owner.startup_feedback_panel.isHidden())
        self.assertEqual(owner.startup_progress.value(), 4)
        self.assertIn("waiting for joinable", owner.lbl_startup_stage.text())
        set_startup_feedback(owner, "Server ready.", step=5, state="complete")
        self.assertEqual(
            owner.startup_feedback_panel.property("startupState"), "complete"
        )

    def test_navigation_panel_emits_selected_view(self) -> None:
        panel = NavigationPanel(
            [NavigationItem("monitor.logs", "Logs")],
            [NavigationItem("config.main", "Config")],
        )
        selected: list[str] = []
        panel.viewSelected.connect(selected.append)

        panel.set_default_selection("config.main")
        panel._emit_selected(panel.config_list.currentItem())

        self.assertEqual(panel.config_list.currentItem().text(), "Config")
        self.assertIn("config.main", selected)
        self.assertFalse(panel.monitor_list.dragEnabled())
        self.assertFalse(panel.config_list.dragEnabled())

    def test_status_renderer_delegates_to_owner_impl(self) -> None:
        class Owner:
            def __init__(self) -> None:
                self.snap = None

            def _apply_status_snapshot_impl(self, snap):
                self.snap = snap

        owner = Owner()
        renderer = StatusRenderer(owner)

        renderer.apply({"server": True})

        self.assertEqual(owner.snap, {"server": True})

    def test_populate_json_tree_builds_nested_nodes(self) -> None:
        tree = QtWidgets.QTreeWidget()
        root = tree.invisibleRootItem()

        populate_json_tree(root, {"player": {"name": "Alice"}, "items": [1, 2]})

        self.assertEqual(root.childCount(), 1)
        obj = root.child(0)
        self.assertEqual(obj.text(0), "object")
        self.assertEqual(obj.child(0).text(0), "player")
        self.assertEqual(obj.child(1).text(0), "items [2]")

    def test_about_text_includes_version_runtime_and_paths(self) -> None:
        text = about_text(
            {
                "suite": "Vein Server Management Suite",
                "version": "2.3.14",
                "commit": "abc1234",
                "mode": "Packaged",
                "python": "3.12.0",
                "os": "Windows 11",
                "license": "Non-Commercial Source Available",
                "repository": "https://example.invalid/repo",
                "app_root": "C:/Program Files/VeinServerManagement",
                "config": "C:/Program Files/VeinServerManagement/Config/config.yaml",
            }
        )

        self.assertIn("Version: 2.3.14", text)
        self.assertIn("Commit: abc1234", text)
        self.assertIn("Mode: Packaged", text)
        self.assertIn("Config:", text)

    def test_server_config_preview_view_builds_expected_widgets(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_server_config_preview_view(owner)

        self.assertIsInstance(widget, QtWidgets.QWidget)
        self.assertIsInstance(owner.treeServerConfigPreview, QtWidgets.QTreeWidget)
        self.assertEqual(owner.treeServerConfigPreview.columnCount(), 5)
        self.assertEqual(owner.btnServerConfigPreviewRefresh.text(), "Refresh")
        self.assertEqual(owner.btnServerConfigEditPreview.text(), "Preview Diff")
        self.assertFalse(owner.btnServerConfigEditApply.isEnabled())
        self.assertEqual(owner.tabsServerSettings.count(), 6)
        self.assertEqual(
            [owner.tabsServerSettings.tabText(index) for index in range(6)],
            ["General", "Access", "Gameplay", "Network", "Discord", "Advanced Settings"],
        )
        self.assertIsInstance(owner.tabsServerSettings.widget(0), QtWidgets.QScrollArea)
        self.assertFalse(owner.frmServerSettingsActions.isHidden())
        self.assertFalse(owner.boxServerSettingsReview.toggle.isChecked())
        self.assertFalse(owner.btnServerIdentityPreview.isEnabled())
        self.assertFalse(owner.btnServerIdentityApply.isEnabled())
        labels = [label.text() for label in widget.findChildren(QtWidgets.QLabel)]
        self.assertFalse(any("settings belong to VEIN" in text for text in labels))
        self.assertTrue(any("These are VEIN Game.ini integrations" in text for text in labels))

        owner.tabsServerSettings.setCurrentIndex(4)
        self.assertFalse(owner.frmServerSettingsActions.isHidden())
        self.assertFalse(owner.boxServerSettingsReview.isHidden())
        owner.tabsServerSettings.setCurrentIndex(5)
        self.assertTrue(owner.frmServerSettingsActions.isHidden())
        self.assertTrue(owner.boxServerSettingsReview.isHidden())
        owner.tabsServerSettings.setCurrentIndex(0)
        self.assertFalse(owner.frmServerSettingsActions.isHidden())

    def test_identity_access_form_loads_tracks_and_validates_curated_values(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_server_config_preview_view(owner)
        items = [
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "ServerName", "value": "Local", "present": True},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "ServerDescription", "value": "Friendly", "present": True},
            {"source": "Game.ini", "section": "/Script/Engine.GameSession", "key": "MaxPlayers", "value": "12", "present": True},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "bPublic", "value": "False", "present": True},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "Password", "value": "<configured, masked>", "present": True},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "AdminSteamIDs", "value": "76561198000000001, 76561198000000002", "present": True},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameSession", "key": "SuperAdminSteamIDs", "value": "(not set)", "present": False},
            {"source": "Game.ini", "section": "/Script/Vein.VeinGameStateBase", "key": "WhitelistedPlayers", "value": "(not set)", "present": False},
        ]

        owner._server_settings_apply_notice = (
            "Changes saved. Validation: PASS=4. Settings take effect on the next start."
        )
        owner._server_settings_apply_notice_kind = "success"
        populate_identity_access_form(owner, items)
        loaded = collect_identity_access_values(owner)
        self.assertEqual(loaded["server_name"], "Local")
        self.assertEqual(loaded["max_players"], 12)
        self.assertFalse(loaded["public"])
        self.assertEqual(len(loaded["admin_steam_ids"]), 2)
        self.assertIn("will be preserved", owner.lblServerIdentityPasswordStatus.text())
        self.assertIn("Validation: PASS=4", owner.lblServerIdentityState.text())
        self.assertFalse(owner.btnServerIdentityPreview.isEnabled())

        owner.edServerIdentityName.clear()
        self.assertIn("required", owner.lblServerIdentityNameError.text())
        self.assertEqual(owner.tabsServerSettings.tabText(0), "General *")
        self.assertFalse(owner.btnServerIdentityPreview.isEnabled())
        owner.edServerIdentityName.setText("Updated")
        self.assertTrue(owner.btnServerIdentityPreview.isEnabled())
        self.assertTrue(owner.btnServerIdentityReset.isEnabled())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_curated_tabs_mark_changes_and_place_validation_by_field(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_server_config_preview_view(owner)
        populate_identity_access_form(owner, [])

        owner.spinServerNetworkGamePort.setValue(27015)
        self.assertEqual(owner.tabsServerSettings.tabText(3), "Network *")
        self.assertIn("must be different", owner.lblServerNetworkPortsError.text())

        owner.edServerDiscordChatWebhook.setText("https://example.invalid/hook")
        self.assertEqual(owner.tabsServerSettings.tabText(4), "Discord *")
        self.assertIn("Discord webhook URL", owner.lblServerDiscordChatError.text())
        self.assertEqual(owner.lblServerDiscordAdminError.text(), "")
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_identity_access_helpers_build_batch_and_mask_secret_diffs(self) -> None:
        discord_webhook = "https://discord.com/" + "api/webhooks/1/secret"
        baseline = {
            "server_name": "Old",
            "server_description": "",
            "max_players": 8,
            "public": True,
            "password": "",
            "admin_steam_ids": ("76561198000000001",),
            "super_admin_steam_ids": (),
            "whitelisted_players": (),
        }
        values = dict(baseline)
        values.update(
            {
                "server_name": "New",
                "public": False,
                "password": "replacement-secret",
                "admin_steam_ids": (),
                "pvp_enabled": False,
                "game_port": 7788,
                "discord_chat_webhook_url": discord_webhook,
            }
        )

        self.assertEqual(validate_identity_access_values(values), {})
        edits = build_identity_access_edits(values, baseline)
        keys = {edit.key for edit in edits}
        self.assertEqual(
            keys,
            {
                "ServerName",
                "bPublic",
                "Password",
                "AdminSteamIDs",
                "vein.PvP",
                "Port",
                "DiscordChatWebhookURL",
            },
        )
        self.assertEqual(next(edit for edit in edits if edit.key == "AdminSteamIDs").values, ())
        summary = identity_access_change_summary(values, baseline)
        self.assertIn("Password", summary)
        self.assertNotIn("replacement-secret", summary)
        self.assertNotIn("/1/secret", summary)

        masked = mask_sensitive_config_diff(
            "--- old\n+++ new\n-Password=old-secret\n+Password=replacement-secret\n"
            f"+DiscordChatWebhookURL={discord_webhook}\n+ServerName=New\n"
        )
        self.assertNotIn("old-secret", masked)
        self.assertNotIn("replacement-secret", masked)
        self.assertNotIn("/1/secret", masked)
        self.assertIn("+Password=<configured, masked>", masked)
        self.assertIn("+ServerName=New", masked)

    def test_identity_access_validation_rejects_invalid_steam_ids(self) -> None:
        values = {
            "server_name": "Server",
            "max_players": 8,
            "admin_steam_ids": ("not-a-steamid",),
            "super_admin_steam_ids": (),
            "whitelisted_players": (),
        }

        errors = validate_identity_access_values(values)

        self.assertIn("admin_steam_ids", errors)
        self.assertIn("17-digit", errors["admin_steam_ids"])

    def test_identity_access_preview_extraction_uses_safe_defaults(self) -> None:
        values = identity_access_values_from_preview([])

        self.assertEqual(values["server_name"], "")
        self.assertEqual(values["max_players"], 8)
        self.assertTrue(values["public"])
        self.assertFalse(values["password_configured"])
        self.assertTrue(values["pvp_enabled"])
        self.assertEqual(values["bind_addr"], "0.0.0.0")
        self.assertEqual(values["game_port"], 7777)
        self.assertFalse(values["discord_chat_webhook_configured"])

    def test_curated_validation_rejects_network_and_discord_errors(self) -> None:
        values = {
            "server_name": "Server",
            "max_players": 8,
            "admin_steam_ids": (),
            "super_admin_steam_ids": (),
            "whitelisted_players": (),
            "bind_addr": "not-an-address",
            "game_port": 7777,
            "query_port": 7777,
            "http_port": 8080,
            "discord_chat_webhook_url": "https://example.invalid/hook",
            "discord_chat_admin_webhook_url": "",
        }

        errors = validate_identity_access_values(values)

        self.assertIn("bind_addr", errors)
        self.assertIn("ports", errors)
        self.assertIn("discord_chat_webhook_url", errors)

    def test_server_config_validation_summary_counts_known_states(self) -> None:
        summary = summarize_server_config_validation(
            [
                {"status": "PASS"},
                {"status": "pass"},
                {"status": "INFO"},
                {"status": "WARN"},
                {"status": "unknown"},
            ]
        )

        self.assertEqual(summary, "Validation: PASS=2, INFO=1, WARN=1")
        self.assertEqual(
            summarize_server_config_validation([]),
            "Validation: no checks reported",
        )

    def test_edit_values_from_text_supports_scalar_and_lists(self) -> None:
        self.assertEqual(edit_values_from_text("One"), "One")
        self.assertEqual(edit_values_from_text("111\n222\n"), ["111", "222"])
        self.assertEqual(edit_values_from_text(" \n "), "")

    def test_quick_start_view_collects_values_and_builds_preview(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        owner.edQuickServerName.setText("Preview Server")
        owner.txtQuickAdmins.setPlainText("111\n222")

        values = collect_quick_start_values(owner)
        preview = build_quick_start_preview(owner)

        self.assertIsInstance(widget, QtWidgets.QScrollArea)
        self.assertTrue(widget.widgetResizable())
        self.assertGreaterEqual(owner.txtQuickServerDescription.minimumHeight(), 64)
        self.assertGreaterEqual(owner.txtQuickStartPreview.minimumHeight(), 140)
        self.assertIsInstance(owner.lblQuickStartStatus, InlineNotice)
        self.assertEqual(owner.btnQuickStartApply.property("buttonRole"), BUTTON_PRIMARY)
        self.assertEqual(values["setup_mode"], "new")
        self.assertFalse(owner.btnQuickStartApply.isEnabled())
        self.assertTrue(owner.edQuickGameLogResolved.isReadOnly())
        self.assertFalse(owner.grpQuickGameLogOverride.isChecked())
        self.assertEqual(values["game_log_override"], "")
        self.assertTrue(owner.edQuickSaveGamesResolved.isReadOnly())
        self.assertFalse(owner.grpQuickSaveGamesOverride.isChecked())
        self.assertEqual(values["save_games_override"], "")
        self.assertEqual(owner.btnQuickStartBrowseRoot.text(), "Browse…")
        self.assertEqual(owner.btnQuickStartBrowseSteamCmd.text(), "Browse…")
        self.assertEqual(values["server_name"], "Preview Server")
        self.assertEqual(values["admin_steam_ids"], ["111", "222"])
        self.assertIn("Server Quick Start Preview", preview)
        self.assertIn("Preview Server", preview)
        self.assertIn("AdminSteamIDs", preview)

    def test_quick_start_wizard_navigation_preserves_form_state(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)

        self.assertEqual(owner.quickStartStack.count(), 4)
        self.assertEqual(owner.quickStartStack.currentIndex(), 0)
        self.assertIn("Step 1 of 4", owner.lblQuickStartStep.text())
        self.assertFalse(owner.btnQuickStartBack.isEnabled())
        self.assertTrue(owner.btnQuickStartLoadExisting.isHidden())
        self.assertTrue(owner.btnQuickStartPreview.isHidden())
        self.assertTrue(owner.btnQuickStartApply.isHidden())

        owner.edQuickServerRoot.setText("D:/Servers/Vein")
        owner.btnQuickStartNext.click()
        owner.edQuickServerName.setText("Persistent Server")
        owner.btnQuickStartNext.click()
        owner.spinQuickGamePort.setValue(7788)
        owner.btnQuickStartNext.click()

        self.assertEqual(owner.quickStartStack.currentIndex(), 3)
        self.assertIn("Review & Apply", owner.lblQuickStartStep.text())
        self.assertTrue(owner.btnQuickStartNext.isHidden())
        self.assertFalse(owner.btnQuickStartPreview.isHidden())
        self.assertFalse(owner.btnQuickStartApply.isHidden())

        set_quick_start_step(owner, 1)
        self.assertEqual(owner.edQuickServerRoot.text(), "D:/Servers/Vein")
        self.assertEqual(owner.edQuickServerName.text(), "Persistent Server")
        self.assertEqual(owner.spinQuickGamePort.value(), 7788)
        self.assertIsInstance(widget, QtWidgets.QScrollArea)

    def test_quick_start_game_log_follows_server_root_until_overridden(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        owner.edQuickServerRoot.setText("D:/Servers/Vein")

        self.assertEqual(
            Path(owner.edQuickGameLogResolved.text()),
            Path("D:/Servers/Vein/Vein/Saved/Logs/Vein.log"),
        )
        self.assertIn("Automatic from Server root", owner.lblQuickGameLogMode.text())

        owner.grpQuickGameLogOverride.setChecked(True)
        owner.edQuickGameLogOverride.setText("E:/Custom/Vein-server.log")
        values = collect_quick_start_values(owner)

        self.assertEqual(
            Path(owner.edQuickGameLogResolved.text()),
            Path("E:/Custom/Vein-server.log"),
        )
        self.assertEqual(values["game_log_override"], "E:/Custom/Vein-server.log")
        self.assertIn("Advanced override active", owner.lblQuickGameLogMode.text())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_save_games_follows_server_root_until_overridden(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        owner.edQuickServerRoot.setText("D:/Servers/Vein")

        self.assertEqual(
            Path(owner.edQuickSaveGamesResolved.text()),
            Path("D:/Servers/Vein/Vein/Saved/SaveGames"),
        )
        self.assertIn("Automatic from Server root", owner.lblQuickSaveGamesMode.text())

        owner.grpQuickSaveGamesOverride.setChecked(True)
        owner.edQuickSaveGamesOverride.setText("E:/Custom/Worlds")
        values = collect_quick_start_values(owner)

        self.assertEqual(Path(owner.edQuickSaveGamesResolved.text()), Path("E:/Custom/Worlds"))
        self.assertEqual(values["save_games_override"], "E:/Custom/Worlds")
        self.assertIn("Advanced override active", owner.lblQuickSaveGamesMode.text())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_config_path_avoids_example_templates(self) -> None:
        class Owner:
            pass

        owner = Owner()
        owner.config_path = "Config/config.example.yaml"
        self.assertIsNone(quick_start_config_path(owner))

        owner.config_path = "Config/config.yaml"
        self.assertEqual(quick_start_config_path(owner), "Config/config.yaml")

    def test_quick_start_existing_mode_imports_values_and_tracks_only_user_changes(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        owner.cmbQuickSetupMode.setCurrentIndex(1)
        set_quick_start_mode(owner, "existing")
        settings = ExistingServerSettings(
            server_root="C:/VeinServer",
            values={
                "server_name": "Imported",
                "max_players": 12,
                "public": False,
                "admin_steam_ids": ["111", "222"],
            },
            loaded_fields=("admin_steam_ids", "max_players", "public", "server_name"),
            missing_files=(),
            password_configured=True,
            discord_chat_webhook_configured=True,
            discord_admin_webhook_configured=False,
        )

        populate_existing_server_settings(owner, settings)
        imported = collect_quick_start_values(owner)
        owner.edQuickServerName.setText("Changed")
        changed = collect_quick_start_values(owner)

        self.assertEqual(imported["existing_loaded_root"], "C:/VeinServer")
        self.assertEqual(imported["server_name"], "Imported")
        self.assertEqual(imported["server_config_fields"], [])
        self.assertEqual(changed["server_config_fields"], ["server_name"])
        self.assertEqual(owner.edQuickPassword.text(), "")
        self.assertIn("existing password is set", owner.lblQuickPasswordStatus.text())
        self.assertIn("existing webhook is configured", owner.lblQuickDiscordChatWebhookStatus.text())
        self.assertIn("no existing webhook", owner.lblQuickDiscordAdminWebhookStatus.text())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_password_status_and_visibility(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        self.assertIn("no password will be set", owner.lblQuickPasswordStatus.text())
        self.assertEqual(owner.edQuickPassword.echoMode(), QtWidgets.QLineEdit.Password)

        owner.edQuickPassword.setText("replacement")
        set_quick_start_password_visibility(owner, True)

        self.assertIn("replacement password entered", owner.lblQuickPasswordStatus.text())
        self.assertEqual(owner.edQuickPassword.echoMode(), QtWidgets.QLineEdit.Normal)
        self.assertEqual(owner.btnQuickPasswordVisibility.text(), "Hide")
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_webhook_status_and_visibility(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        self.assertIn("no webhook will be set", owner.lblQuickDiscordChatWebhookStatus.text())
        self.assertEqual(owner.edQuickDiscordChatWebhook.echoMode(), QtWidgets.QLineEdit.Password)

        owner.edQuickDiscordChatWebhook.setText(
            "https://discord.com/api/" + "webhooks/1/token"
        )
        set_quick_start_webhook_visibility(
            owner.edQuickDiscordChatWebhook,
            owner.btnQuickDiscordChatWebhookVisibility,
            True,
        )

        self.assertIn("replacement URL entered", owner.lblQuickDiscordChatWebhookStatus.text())
        self.assertEqual(owner.edQuickDiscordChatWebhook.echoMode(), QtWidgets.QLineEdit.Normal)
        self.assertEqual(owner.btnQuickDiscordChatWebhookVisibility.text(), "Hide")
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_separates_app_and_game_webhooks_with_reuse_options(self) -> None:
        class Owner:
            config_path = ""

        owner = Owner()
        widget = build_quick_start_view(owner)
        webhook = "https://discord.com/api/" + "webhooks/1/token"
        owner.edQuickManagementWebhook.setText(webhook)
        owner.chkQuickUseManagementForChat.setChecked(True)
        owner.chkQuickUseManagementForAdmin.setChecked(True)

        values = collect_quick_start_values(owner)
        preview = build_quick_start_preview(owner)

        self.assertEqual(values["management_discord_webhook"], webhook)
        self.assertEqual(values["discord_chat_webhook_url"], webhook)
        self.assertEqual(values["discord_chat_admin_webhook_url"], webhook)
        self.assertFalse(owner.edQuickDiscordChatWebhook.isEnabled())
        self.assertFalse(owner.edQuickDiscordAdminWebhook.isEnabled())
        self.assertIn("<configured, masked>", preview)
        self.assertNotIn(webhook, preview)

        owner.edQuickManagementWebhook.setText("ENV:DISCORD_WEBHOOK_URL")
        self.assertIn(
            "ENV reference cannot be reused",
            owner.lblQuickDiscordChatWebhookStatus.text(),
        )
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_detected_server_forces_existing_mode(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        inspection = ServerRootInspection(
            state="existing",
            server_root="C:/VeinServer",
            indicators=("C:/VeinServer/Vein/Binaries/Win64/VeinServer.exe",),
        )

        changed = enforce_quick_start_root_mode(owner, inspection)

        self.assertTrue(changed)
        self.assertIsInstance(widget, QtWidgets.QWidget)
        self.assertEqual(owner.cmbQuickSetupMode.currentData(), "existing")
        self.assertEqual(owner._quick_start_auto_detected_root, "C:/VeinServer")

    def test_quick_start_routes_installer_server_to_first_setup_wizard(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        route_quick_start_workflow(
            owner,
            SetupAssessment(
                SetupState.FIRST_SETUP,
                SetupWorkflow.FIRST_SETUP,
                "Finish Server Setup",
                "Installed by SteamCMD and awaiting configuration.",
            ),
            SetupMetadata(source="installer_new"),
        )

        values = collect_quick_start_values(owner)
        self.assertEqual(owner.cmbQuickSetupMode.currentData(), "new")
        self.assertEqual(values["setup_workflow"], "first_setup")
        self.assertEqual(values["setup_source"], "installer_new")
        self.assertFalse(owner.lblQuickStartStep.isHidden())
        self.assertTrue(owner.btnQuickStartLoadExisting.isHidden())
        self.assertIsInstance(widget, QtWidgets.QWidget)

    def test_quick_start_routes_configured_server_to_settings_action(self) -> None:
        class Owner:
            pass

        owner = Owner()
        widget = build_quick_start_view(owner)
        route_quick_start_workflow(
            owner,
            SetupAssessment(
                SetupState.CONFIGURED,
                SetupWorkflow.EXISTING_SERVER,
                "Edit Server Settings",
                "Setup is complete.",
            ),
            SetupMetadata(completed=True, source="existing_import"),
        )

        self.assertEqual(owner.cmbQuickSetupMode.currentData(), "existing")
        self.assertFalse(owner.btnQuickStartOpenSettings.isHidden())
        self.assertTrue(owner.btnQuickStartLoadExisting.isHidden())
        self.assertTrue(owner.btnQuickStartConnectExisting.isHidden())
        self.assertIn("already configured", owner.lblQuickStartStatus.text())
        self.assertIsInstance(widget, QtWidgets.QWidget)


if __name__ == "__main__":
    unittest.main()
