from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CTRL = ROOT / "Controller"
if str(CTRL) not in sys.path:
    sys.path.insert(0, str(CTRL))

from Tools import backup_restore  # noqa: E402
from Tools.backup_pins import is_archive_pinned  # noqa: E402


class GuardedRestoreTests(unittest.TestCase):
    def _archive(
        self,
        path: Path,
        payload: bytes,
        reason: str = "Manual",
        save_filename: str = "Server.vns",
    ) -> Path:
        manifest = {
            "reason": reason,
            "created_utc": "2026-07-23T12:00:00Z",
            "save_filename": save_filename,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "version": 1,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as bundle:
            bundle.writestr(save_filename, payload)
            bundle.writestr("manifest.json", json.dumps(manifest))
        return path

    def _fixture(self, root: Path):
        save_dir = root / "SaveGames"
        save_dir.mkdir()
        live = save_dir / "Server.vns"
        live.write_bytes(b"current live save")
        selected = self._archive(root / "selected.zip", b"restored save")
        safety = root / "Backups" / "BeforeRestore" / "safety.zip"

        def create_safety(source: Path) -> Path:
            return self._archive(safety, source.read_bytes(), "BeforeRestore")

        return save_dir, live, selected, safety, create_safety

    def test_guarded_restore_creates_pinned_safety_point_and_replaces_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, safety, create_safety = self._fixture(root)

            result = backup_restore.guarded_restore(
                selected,
                save_dir=save_dir,
                operation_dir=root / "Runtime",
                server_running_check=lambda: False,
                create_safety_backup=create_safety,
            )

            self.assertEqual(live.read_bytes(), b"restored save")
            self.assertEqual(result.safety_backup, str(safety))
            self.assertTrue(is_archive_pinned(safety))
            state = json.loads(
                (root / "Runtime" / "restore.state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["phase"], "complete")
            self.assertFalse((root / "Runtime" / "restore.lock").exists())
            self.assertEqual(list(save_dir.glob(".vein-restore-*.tmp")), [])

    def test_running_server_blocks_before_safety_backup_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, create_safety = self._fixture(root)
            create = mock.Mock(side_effect=create_safety)

            with self.assertRaisesRegex(backup_restore.GuardedRestoreError, "Stop the server"):
                backup_restore.guarded_restore(
                    selected,
                    save_dir=save_dir,
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: True,
                    create_safety_backup=create,
                )

            self.assertEqual(live.read_bytes(), b"current live save")
            create.assert_not_called()

    def test_invalid_safety_backup_aborts_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, _create_safety = self._fixture(root)
            invalid = root / "invalid.zip"
            invalid.write_bytes(b"not a zip")

            with self.assertRaisesRegex(
                backup_restore.GuardedRestoreError, "safety backup did not pass"
            ):
                backup_restore.guarded_restore(
                    selected,
                    save_dir=save_dir,
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: False,
                    create_safety_backup=lambda _source: invalid,
                )

            self.assertEqual(live.read_bytes(), b"current live save")

    def test_valid_but_wrong_safety_backup_aborts_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, _create_safety = self._fixture(root)
            wrong = self._archive(
                root / "Backups" / "BeforeRestore" / "wrong.zip",
                b"different save",
                "BeforeRestore",
            )

            with self.assertRaisesRegex(
                backup_restore.GuardedRestoreError, "does not match"
            ):
                backup_restore.guarded_restore(
                    selected,
                    save_dir=save_dir,
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: False,
                    create_safety_backup=lambda _source: wrong,
                )

            self.assertEqual(live.read_bytes(), b"current live save")
            self.assertFalse(is_archive_pinned(wrong))

    def test_invalid_selected_archive_never_creates_safety_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, _selected, _safety, create_safety = self._fixture(root)
            invalid = root / "invalid.zip"
            invalid.write_bytes(b"not a zip")
            create = mock.Mock(side_effect=create_safety)

            with self.assertRaisesRegex(
                backup_restore.GuardedRestoreError, "did not pass restore validation"
            ):
                backup_restore.guarded_restore(
                    invalid,
                    save_dir=save_dir,
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: False,
                    create_safety_backup=create,
                )

            self.assertEqual(live.read_bytes(), b"current live save")
            create.assert_not_called()
            status = backup_restore.inspect_restore_operation(root / "Runtime")
            self.assertEqual(status.phase, "failed_no_change")
            self.assertEqual(status.kind, "warning")

    def test_server_start_during_staging_aborts_before_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, create_safety = self._fixture(root)
            states = iter((False, True))

            with self.assertRaisesRegex(backup_restore.GuardedRestoreError, "started"):
                backup_restore.guarded_restore(
                    selected,
                    save_dir=save_dir,
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: next(states),
                    create_safety_backup=create_safety,
                )

            self.assertEqual(live.read_bytes(), b"current live save")

    def test_post_replace_verification_failure_rolls_back_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, safety, create_safety = self._fixture(root)
            original_verify = backup_restore._verify_hash

            def fail_replacement(path: Path, expected: str) -> bool:
                if path == live and path.read_bytes() == b"restored save":
                    return False
                return original_verify(path, expected)

            with mock.patch.object(
                backup_restore, "_verify_hash", side_effect=fail_replacement
            ):
                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "Post-restore verification"
                ):
                    backup_restore.guarded_restore(
                        selected,
                        save_dir=save_dir,
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                        create_safety_backup=create_safety,
                    )

            self.assertEqual(live.read_bytes(), b"current live save")
            self.assertTrue(is_archive_pinned(safety))

    def test_atomic_replace_failure_keeps_original_and_pinned_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, safety, create_safety = self._fixture(root)
            original_replace = backup_restore.os.replace

            def fail_stage_replace(source: Path, destination: Path) -> None:
                if "restore-stage" in Path(source).name:
                    raise OSError("replace failed")
                original_replace(source, destination)

            with mock.patch.object(
                backup_restore.os, "replace", side_effect=fail_stage_replace
            ):
                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "replace failed"
                ):
                    backup_restore.guarded_restore(
                        selected,
                        save_dir=save_dir,
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                        create_safety_backup=create_safety,
                    )

            self.assertEqual(live.read_bytes(), b"current live save")
            self.assertTrue(is_archive_pinned(safety))
            self.assertEqual(list(save_dir.glob(".vein-restore-stage-*.tmp")), [])

    def test_pin_failure_aborts_before_staging_or_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, create_safety = self._fixture(root)

            with mock.patch.object(
                backup_restore, "pin_backup", side_effect=OSError("pin failed")
            ):
                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "pin failed"
                ):
                    backup_restore.guarded_restore(
                        selected,
                        save_dir=save_dir,
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                        create_safety_backup=create_safety,
                    )

            self.assertEqual(live.read_bytes(), b"current live save")
            self.assertEqual(list(save_dir.glob(".vein-restore-stage-*.tmp")), [])

    def test_existing_lock_blocks_concurrent_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, _safety, create_safety = self._fixture(root)
            runtime = root / "Runtime"
            runtime.mkdir()
            (runtime / "restore.lock").write_text("existing", encoding="utf-8")
            journal = runtime / "restore.state.json"
            journal.write_text(
                json.dumps({"phase": "staging", "operation_id": "first"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(backup_restore.GuardedRestoreError, "active"):
                backup_restore.guarded_restore(
                    selected,
                    save_dir=save_dir,
                    operation_dir=runtime,
                    server_running_check=lambda: False,
                    create_safety_backup=create_safety,
                )

            self.assertEqual(live.read_bytes(), b"current live save")
            self.assertEqual(
                json.loads(journal.read_text(encoding="utf-8"))["operation_id"],
                "first",
            )

    def test_failed_rollback_preserves_recovery_copy_and_pinned_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir, live, selected, safety, create_safety = self._fixture(root)
            original_verify = backup_restore._verify_hash
            original_replace = backup_restore.os.replace

            def fail_replacement_verification(path: Path, expected: str) -> bool:
                if path == live and path.read_bytes() == b"restored save":
                    return False
                return original_verify(path, expected)

            def fail_rollback(source: Path, destination: Path) -> None:
                if "rollback" in Path(source).name:
                    raise OSError("rollback rename failed")
                original_replace(source, destination)

            with mock.patch.object(
                backup_restore, "_verify_hash", side_effect=fail_replacement_verification
            ), mock.patch.object(
                backup_restore.os, "replace", side_effect=fail_rollback
            ):
                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "could not be verified"
                ):
                    backup_restore.guarded_restore(
                        selected,
                        save_dir=save_dir,
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                        create_safety_backup=create_safety,
                    )

            recovery = list(save_dir.glob(".vein-restore-rollback-*.tmp"))
            self.assertEqual(len(recovery), 1)
            self.assertEqual(recovery[0].read_bytes(), b"current live save")
            self.assertTrue(is_archive_pinned(safety))
            state = json.loads(
                (root / "Runtime" / "restore.state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["phase"], "rollback_failed")
            status = backup_restore.inspect_restore_operation(root / "Runtime")
            self.assertEqual(status.kind, "error")
            self.assertIn("Do not start", status.guidance)
            self.assertEqual(status.rollback_copy, str(recovery[0]))

    def test_restore_operation_status_detects_active_and_interrupted_phases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            journal = runtime / "restore.state.json"
            journal.write_text(
                json.dumps({"phase": "staging", "safety_backup": "safety.zip"}),
                encoding="utf-8",
            )

            interrupted = backup_restore.inspect_restore_operation(runtime)
            self.assertEqual(interrupted.kind, "error")
            self.assertIn("interrupted", interrupted.summary)

            (runtime / "restore.lock").write_text("active", encoding="utf-8")
            active = backup_restore.inspect_restore_operation(runtime)
            self.assertEqual(active.kind, "active")
            self.assertTrue(active.visible)

    def test_restore_operation_status_hides_completed_and_reports_bad_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            journal = runtime / "restore.state.json"
            journal.write_text(json.dumps({"phase": "complete"}), encoding="utf-8")

            complete = backup_restore.inspect_restore_operation(runtime)
            self.assertEqual(complete.kind, "complete")
            self.assertFalse(complete.visible)

            journal.write_text("not json", encoding="utf-8")
            unreadable = backup_restore.inspect_restore_operation(runtime)
            self.assertEqual(unreadable.phase, "unreadable")
            self.assertEqual(unreadable.kind, "error")

    def test_startup_recovery_uses_newest_valid_archive_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = root / "SaveGames"
            save_dir.mkdir()
            invalid = root / "newest.zip"
            invalid.write_bytes(b"not a zip")
            valid = self._archive(root / "older.zip", b"recovered save")

            result = backup_restore.recover_missing_save(
                [invalid, valid],
                save_dir=save_dir,
                expected_filenames=["Server.vns"],
                operation_dir=root / "Runtime",
                server_running_check=lambda: False,
            )

            self.assertEqual((save_dir / "Server.vns").read_bytes(), b"recovered save")
            self.assertEqual(result.archive, str(valid))
            state = json.loads(
                (root / "Runtime" / "startup_recovery.state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(state["phase"], "complete")

    def test_startup_recovery_never_replaces_an_existing_or_empty_save(self) -> None:
        for payload in (b"live", b""):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                save_dir = root / "SaveGames"
                save_dir.mkdir()
                live = save_dir / "Server.vns"
                live.write_bytes(payload)
                archive = self._archive(root / "backup.zip", b"backup")

                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "live save appeared"
                ):
                    backup_restore.recover_missing_save(
                        [archive],
                        save_dir=save_dir,
                        expected_filenames=["Server.vns"],
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                    )

                self.assertEqual(live.read_bytes(), payload)

    def test_startup_recovery_rechecks_server_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = root / "SaveGames"
            save_dir.mkdir()
            archive = self._archive(root / "backup.zip", b"backup")
            states = iter((False, True))

            with self.assertRaisesRegex(
                backup_restore.GuardedRestoreError, "started during recovery"
            ):
                backup_restore.recover_missing_save(
                    [archive],
                    save_dir=save_dir,
                    expected_filenames=["Server.vns"],
                    operation_dir=root / "Runtime",
                    server_running_check=lambda: next(states),
                )

            self.assertFalse((save_dir / "Server.vns").exists())

    def test_startup_recovery_lock_blocks_parallel_manual_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = root / "SaveGames"
            save_dir.mkdir()
            runtime = root / "Runtime"
            runtime.mkdir()
            lock = runtime / "restore.lock"
            lock.write_text("manual-restore", encoding="utf-8")
            archive = self._archive(root / "backup.zip", b"backup")

            with self.assertRaisesRegex(
                backup_restore.GuardedRestoreError, "Another restore operation"
            ):
                backup_restore.recover_missing_save(
                    [archive],
                    save_dir=save_dir,
                    expected_filenames=["Server.vns"],
                    operation_dir=runtime,
                    server_running_check=lambda: False,
                )

            self.assertEqual(lock.read_text(encoding="utf-8"), "manual-restore")
            self.assertFalse((save_dir / "Server.vns").exists())

    def test_startup_recovery_skips_archive_for_another_save_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = root / "SaveGames"
            save_dir.mkdir()
            wrong = self._archive(
                root / "newest.zip",
                b"other world",
                save_filename="Other.vns",
            )
            valid = self._archive(root / "older.zip", b"expected world")

            result = backup_restore.recover_missing_save(
                [wrong, valid],
                save_dir=save_dir,
                expected_filenames=["Server.vns"],
                operation_dir=root / "Runtime",
                server_running_check=lambda: False,
            )

            self.assertEqual(result.archive, str(valid))
            self.assertEqual((save_dir / "Server.vns").read_bytes(), b"expected world")
            self.assertFalse((save_dir / "Other.vns").exists())

    def test_failed_startup_post_write_verification_preserves_unverified_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_dir = root / "SaveGames"
            save_dir.mkdir()
            archive = self._archive(root / "backup.zip", b"candidate")
            original_verify = backup_restore._verify_hash

            def fail_live_verification(path: Path, expected: str) -> bool:
                if path == save_dir / "Server.vns":
                    return False
                return original_verify(path, expected)

            with mock.patch.object(
                backup_restore, "_verify_hash", side_effect=fail_live_verification
            ):
                with self.assertRaisesRegex(
                    backup_restore.GuardedRestoreError, "post-write verification"
                ):
                    backup_restore.recover_missing_save(
                        [archive],
                        save_dir=save_dir,
                        expected_filenames=["Server.vns"],
                        operation_dir=root / "Runtime",
                        server_running_check=lambda: False,
                    )

            self.assertFalse((save_dir / "Server.vns").exists())
            failed = list(save_dir.glob(".vein-recovery-failed-*.tmp"))
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0].read_bytes(), b"candidate")
            state = json.loads(
                (root / "Runtime" / "startup_recovery.state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(state["phase"], "failed")
            self.assertEqual(state["unverified_recovery_copy"], str(failed[0]))


if __name__ == "__main__":
    unittest.main()
