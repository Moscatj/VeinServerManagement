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
from GUI.server_config_view import build_server_config_preview_view, edit_values_from_text  # noqa: E402
from GUI.status_view import StatusRenderer  # noqa: E402
from GUI.widgets import CollapsibleBox  # noqa: E402


def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class GuiHelperTests(unittest.TestCase):
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

    def test_edit_values_from_text_supports_scalar_and_lists(self) -> None:
        self.assertEqual(edit_values_from_text("One"), "One")
        self.assertEqual(edit_values_from_text("111\n222\n"), ["111", "222"])
        self.assertEqual(edit_values_from_text(" \n "), "")


if __name__ == "__main__":
    unittest.main()
