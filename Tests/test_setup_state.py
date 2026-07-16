from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools.setup_state import (  # noqa: E402
    SetupMetadata,
    SetupState,
    SetupWorkflow,
    classify_setup_state,
    normalize_server_root,
    setup_metadata_update,
)


class SetupStateTests(unittest.TestCase):
    def assess(
        self,
        *,
        binaries: bool,
        meaningful: bool = False,
        completed: bool = False,
        source: str = "unconfigured",
        recorded_root: str = "C:/Servers/Vein",
        current_root: str = "C:/Servers/Vein",
    ):
        return classify_setup_state(
            server_root=current_root,
            binaries_present=binaries,
            meaningful_config_present=meaningful,
            metadata=SetupMetadata(
                completed=completed,
                server_root=recorded_root,
                source=source,
            ),
        )

    def test_missing_unconfigured_server_routes_to_install(self) -> None:
        assessment = self.assess(binaries=False)
        self.assertEqual(assessment.state, SetupState.NEW_OR_MISSING)
        self.assertEqual(assessment.workflow, SetupWorkflow.NEW_SERVER)
        self.assertEqual(assessment.primary_action, "Install Server")

    def test_installer_provisioned_server_routes_to_first_setup(self) -> None:
        assessment = self.assess(binaries=True, source="installer_new")
        self.assertEqual(assessment.state, SetupState.FIRST_SETUP)
        self.assertEqual(assessment.workflow, SetupWorkflow.FIRST_SETUP)

    def test_unconfigured_binaries_without_meaningful_config_route_to_first_setup(self) -> None:
        assessment = self.assess(binaries=True)
        self.assertEqual(assessment.state, SetupState.FIRST_SETUP)

    def test_meaningful_external_config_routes_to_existing_import(self) -> None:
        assessment = self.assess(binaries=True, meaningful=True)
        self.assertEqual(assessment.state, SetupState.EXISTING_UNREGISTERED)
        self.assertEqual(assessment.workflow, SetupWorkflow.EXISTING_SERVER)

    def test_completed_matching_server_routes_to_everyday_settings(self) -> None:
        assessment = self.assess(binaries=True, meaningful=True, completed=True)
        self.assertEqual(assessment.state, SetupState.CONFIGURED)
        self.assertEqual(assessment.primary_action, "Edit Server Settings")

    def test_completed_server_with_missing_binaries_routes_to_repair(self) -> None:
        assessment = self.assess(binaries=False, completed=True)
        self.assertEqual(assessment.state, SetupState.REPAIR_MISSING)
        self.assertEqual(assessment.primary_action, "Repair Missing Server")

    def test_completed_record_for_different_root_requires_operator_choice(self) -> None:
        assessment = self.assess(
            binaries=True,
            meaningful=True,
            completed=True,
            current_root="D:/Other/Vein",
        )
        self.assertEqual(assessment.state, SetupState.AMBIGUOUS)
        self.assertEqual(assessment.primary_action, "Choose Server Intent")

    def test_metadata_parser_is_conservative_for_unknown_values(self) -> None:
        metadata = SetupMetadata.from_config(
            {
                "setup": {
                    "schema_version": "1",
                    "completed": True,
                    "server_root": "C:/Vein",
                    "source": "unexpected",
                }
            }
        )
        self.assertEqual(metadata.schema_version, 1)
        self.assertEqual(metadata.source, "unknown")
        self.assertTrue(metadata.completed)

    def test_metadata_update_records_normalized_root_and_completion_time(self) -> None:
        with TemporaryDirectory(dir=ROOT) as tmp:
            block = setup_metadata_update(
                "Server",
                source="quick_start_new",
                completed=True,
                completed_at="2026-07-15T12:00:00+00:00",
                base_dir=tmp,
            )
            self.assertEqual(block["server_root"], normalize_server_root("Server", base_dir=tmp))
        self.assertTrue(block["completed"])
        self.assertEqual(block["source"], "quick_start_new")
        self.assertEqual(block["completed_at"], "2026-07-15T12:00:00+00:00")

    def test_incomplete_metadata_never_keeps_a_stale_completion_time(self) -> None:
        block = setup_metadata_update(
            "C:/Vein",
            source="installer_new",
            completed=False,
            completed_at="stale",
        )
        self.assertFalse(block["completed"])
        self.assertEqual(block["completed_at"], "")


if __name__ == "__main__":
    unittest.main()
