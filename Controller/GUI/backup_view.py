"""Backup history, policy controls, and protected restore-point metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from PySide6 import QtCore, QtWidgets

from Tools.backups import list_backup_archives, make_backup
from Tools.backup_pins import pin_backup, remove_backup_pin, update_backup_pin
from Tools.backup_restore_preview import inspect_restore_archive
from Tools.backup_restore import guarded_restore, inspect_restore_operation
from Tools.process import is_server_running
from Tools.backup_policy import (
    BackupPolicy,
    apply_backup_policy,
    backup_policy_summary,
    load_backup_policy,
)
from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    CONTROL_SPACING,
    InlineNotice,
    PAGE_MARGIN,
    SECTION_SPACING,
    PageHeader,
    set_button_role,
)
from .widgets import CollapsibleBox

BACKUP_HISTORY_DISPLAY_LIMIT = 200


def format_archive_size(size_bytes: int) -> str:
    """Format archive bytes for a compact history table."""
    size = max(0, int(size_bytes))
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def backup_history_summary(
    archives: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize already-discovered archives without touching the filesystem."""
    if not archives:
        return {
            "count": 0,
            "size_bytes": 0,
            "categories": 0,
            "newest": "",
            "oldest": "",
        }
    return {
        "count": len(archives),
        "size_bytes": sum(int(item.get("size_bytes") or 0) for item in archives),
        "categories": len({str(item.get("category") or "Root") for item in archives}),
        "newest": str(archives[0].get("modified") or ""),
        "oldest": str(archives[-1].get("modified") or ""),
    }


def filter_backup_archives(
    archives: Sequence[Mapping[str, Any]],
    category: str = "",
    *,
    pinned_only: bool = False,
    limit: int = BACKUP_HISTORY_DISPLAY_LIMIT,
) -> list[Mapping[str, Any]]:
    """Return the newest archives matching one category for table display."""
    matches = [
        archive
        for archive in archives
        if (not category or str(archive.get("category") or "Root") == category)
        and (not pinned_only or bool(archive.get("pinned")))
    ]
    return matches[: max(1, int(limit))]


class BackupHistorySignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class BackupHistoryWorker(QtCore.QRunnable):
    """Scan a configured backup root without blocking the GUI thread."""

    def __init__(
        self,
        root: str | Path,
        *,
        limit: int | None = None,
        operation_dir: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.root = Path(root)
        self.limit = limit
        self.operation_dir = Path(operation_dir) if operation_dir else None
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            archives = list_backup_archives(self.root, limit=self.limit)
            payload = {
                "ok": True,
                "root": str(self.root),
                "archives": [archive.as_dict() for archive in archives],
                "restore_status": (
                    inspect_restore_operation(self.operation_dir).as_dict()
                    if self.operation_dir
                    else {}
                ),
                "error": "",
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "root": str(self.root),
                "archives": [],
                "restore_status": {},
                "error": str(exc),
            }
        self.signals.ready.emit(payload)


class RestorePointWorker(QtCore.QRunnable):
    """Protect an existing or freshly created backup as a restore point."""

    def __init__(
        self,
        *,
        action: str,
        label: str = "",
        note: str = "",
        archive: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.action = action
        self.label = label
        self.note = note
        self.archive = Path(archive) if archive else None
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            archive = self.archive
            if self.action == "create":
                archive = make_backup("RestorePoint")
            if archive is None:
                raise ValueError("No backup archive was selected.")
            if self.action == "remove":
                remove_backup_pin(archive)
                pin_payload = {}
            elif self.action == "edit":
                pin_payload = update_backup_pin(
                    archive, label=self.label, note=self.note
                ).as_dict()
            else:
                pin_payload = pin_backup(
                    archive, label=self.label, note=self.note
                ).as_dict()
            payload = {
                "ok": True,
                "action": self.action,
                "archive": str(archive),
                "pin": pin_payload,
                "error": "",
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "action": self.action,
                "archive": str(self.archive or ""),
                "pin": {},
                "error": str(exc),
            }
        self.signals.ready.emit(payload)


class RestorePreviewWorker(QtCore.QRunnable):
    """Validate a possible restore source without extracting or writing it."""

    def __init__(
        self,
        archive: str | Path,
        *,
        save_dir: str | Path,
        server_running: bool,
    ) -> None:
        super().__init__()
        self.archive = Path(archive)
        self.save_dir = Path(save_dir)
        self.server_running = bool(server_running)
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            preview = inspect_restore_archive(
                self.archive,
                save_dir=self.save_dir,
                server_running=self.server_running,
            )
            payload = {"ok": True, "preview": preview.as_dict(), "error": ""}
        except Exception as exc:
            payload = {"ok": False, "preview": {}, "error": str(exc)}
        self.signals.ready.emit(payload)


class GuardedRestoreWorker(QtCore.QRunnable):
    """Run the guarded restore engine without blocking the GUI thread."""

    def __init__(
        self,
        archive: str | Path,
        *,
        save_dir: str | Path,
        operation_dir: str | Path,
    ) -> None:
        super().__init__()
        self.archive = Path(archive)
        self.save_dir = Path(save_dir)
        self.operation_dir = Path(operation_dir)
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            def create_safety_backup(source: Path) -> Path:
                archive = make_backup("BeforeRestore", files=[source])
                if archive is None:
                    raise RuntimeError("Before Restore safety backup was not created.")
                return Path(archive)

            result = guarded_restore(
                self.archive,
                save_dir=self.save_dir,
                operation_dir=self.operation_dir,
                server_running_check=is_server_running,
                create_safety_backup=create_safety_backup,
            )
            payload = {"ok": True, "result": result.as_dict(), "error": ""}
        except Exception as exc:
            payload = {"ok": False, "result": {}, "error": str(exc)}
        self.signals.ready.emit(payload)


def prompt_restore_point_details(
    parent: QtWidgets.QWidget,
    *,
    title: str,
    initial_label: str = "",
    initial_note: str = "",
) -> tuple[str, str] | None:
    """Collect a required short label and optional note in one compact dialog."""
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(480)
    layout = QtWidgets.QVBoxLayout(dialog)
    message = QtWidgets.QLabel(
        "Give this protected backup a name you will recognize later. "
        "Restore points are excluded from automatic cleanup."
    )
    message.setWordWrap(True)
    layout.addWidget(message)
    form = QtWidgets.QFormLayout()
    label = QtWidgets.QLineEdit()
    label.setMaxLength(80)
    label.setPlaceholderText("Example: Before server migration")
    label.setText(initial_label)
    note = QtWidgets.QPlainTextEdit()
    note.setMaximumHeight(90)
    note.setPlaceholderText("Optional context about this rollback point")
    note.setPlainText(initial_note)
    form.addRow("Label", label)
    form.addRow("Note", note)
    layout.addLayout(form)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
    )
    save = buttons.button(QtWidgets.QDialogButtonBox.Save)
    save.setEnabled(bool(initial_label.strip()))
    label.textChanged.connect(lambda text: save.setEnabled(bool(text.strip())))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    label.setFocus()
    if dialog.exec() != QtWidgets.QDialog.Accepted:
        return None
    return label.text().strip(), note.toPlainText().strip()


def build_restore_preview_dialog(
    parent: QtWidgets.QWidget | None,
    payload: Mapping[str, Any],
    *,
    allow_restore: bool = False,
) -> QtWidgets.QDialog:
    """Build restore assessment and, when allowed, final confirmation."""
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle("Restore Preview")
    dialog.setMinimumSize(680, 520)
    layout = QtWidgets.QVBoxLayout(dialog)

    ready = bool(payload.get("ready_for_guarded_restore"))
    errors = [str(item) for item in payload.get("errors") or []]
    warnings = [str(item) for item in payload.get("warnings") or []]
    status = InlineNotice()
    if ready:
        status.setText(
            "Archive validation passed, the current save is present, and the server is stopped."
        )
        status.set_kind("success")
    else:
        status.setText(
            "This archive is not ready for a guarded restore. Review the findings below. "
            "No files were changed."
        )
        status.set_kind("warning" if not errors else "error")
    layout.addWidget(status)

    form = QtWidgets.QFormLayout()
    fields = (
        ("Archive", payload.get("archive") or "Unknown"),
        ("Archive size", format_archive_size(int(payload.get("archive_size") or 0))),
        ("Restore point", payload.get("restore_point_label") or "No"),
        ("Restore-point note", payload.get("restore_point_note") or "None"),
        ("Backup type", payload.get("reason") or "Unknown"),
        (
            "Backup created",
            payload.get("created_utc")
            or payload.get("archive_modified")
            or "Unknown",
        ),
        ("Contained save", payload.get("save_member") or "Not validated"),
        ("Save size", format_archive_size(int(payload.get("save_size") or 0))),
        (
            "Manifest and save hash",
            "Verified" if payload.get("manifest_valid") else "Not verified",
        ),
        ("Live-save destination", payload.get("destination") or "Unknown"),
        ("Current live save", "Present" if payload.get("destination_exists") else "Not found"),
        ("Server state", "Running - stop required" if payload.get("server_running") else "Stopped"),
    )
    for label, value in fields:
        text = QtWidgets.QLabel(str(value))
        text.setWordWrap(True)
        text.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        form.addRow(label, text)
    layout.addLayout(form)

    findings = QtWidgets.QGroupBox("Validation findings")
    findings_layout = QtWidgets.QVBoxLayout(findings)
    messages = errors + warnings
    if messages:
        for message in messages:
            finding = QtWidgets.QLabel(f"- {message}")
            finding.setWordWrap(True)
            findings_layout.addWidget(finding)
    else:
        findings_layout.addWidget(QtWidgets.QLabel("No validation problems found."))
    layout.addWidget(findings)

    plan = InlineNotice(
        "Guarded restore will create and protect a fresh "
        "Before Restore backup of the current save; stage and validate the selected "
        "save; then replace the live save atomically with a rollback path."
    )
    plan.set_kind("info")
    layout.addWidget(plan)
    can_restore = bool(ready and allow_restore)
    if can_restore:
        consequence = InlineNotice(
            "The selected backup will become the active server save. The current save "
            "will remain available as a protected Before Restore point. The server will "
            "remain stopped after completion."
        )
        consequence.set_kind("warning")
        layout.addWidget(consequence)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Cancel
        )
        restore = buttons.addButton(
            "Restore Selected Backup", QtWidgets.QDialogButtonBox.AcceptRole
        )
        set_button_role(restore, BUTTON_PRIMARY)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
    else:
        preview_only = QtWidgets.QLabel(
            "Preview only. Restore requires a valid archive, an existing live save, "
            "a stopped server, and enabled save backups for the mandatory safety point."
        )
        preview_only.setProperty("fieldHelp", True)
        layout.addWidget(preview_only)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return dialog


class BackupPolicyWorker(QtCore.QRunnable):
    """Load or apply backup policy outside the GUI thread."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        action: str,
        policy: BackupPolicy | None = None,
    ) -> None:
        super().__init__()
        self.config_path = Path(config_path)
        self.action = action
        self.policy = policy
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            if self.action == "apply":
                if self.policy is None:
                    raise ValueError("No backup policy was supplied.")
                result = apply_backup_policy(self.config_path, self.policy)
                payload = result.as_dict()
            else:
                policy = load_backup_policy(self.config_path)
                payload = {"changed": False, "backup": "", "policy": policy.as_dict()}
            payload.update({"ok": True, "action": self.action, "error": ""})
        except Exception as exc:
            payload = {
                "ok": False,
                "action": self.action,
                "error": str(exc),
                "changed": False,
                "backup": "",
                "policy": {},
            }
        self.signals.ready.emit(payload)


def collect_backup_policy(owner) -> BackupPolicy:
    return BackupPolicy(
        enabled=owner.chkBackupPolicyEnabled.isChecked(),
        startup_recovery_enabled=owner.chkBackupStartupRecovery.isChecked(),
        on_autosave=owner.chkBackupPolicyAutosave.isChecked(),
        on_crash_detect=owner.chkBackupPolicyCrash.isChecked(),
        on_shutdown=owner.chkBackupPolicyShutdown.isChecked(),
        cleanup_enabled=owner.chkBackupPolicyCleanupEnabled.isChecked(),
        cleanup_by_count=owner.chkBackupPolicyCleanupCount.isChecked(),
        cleanup_by_age=owner.chkBackupPolicyCleanupAge.isChecked(),
        minimum_backups=owner.spinBackupPolicyMinimum.value(),
        max_backups=owner.spinBackupPolicyCount.value(),
        max_age_days=owner.spinBackupPolicyAge.value(),
    )


def backup_retention_explanation(policy: BackupPolicy) -> str:
    modes = []
    if policy.cleanup_by_count:
        modes.append(f"maximum {policy.max_backups}")
    if policy.cleanup_by_age:
        modes.append(f"age {policy.max_age_days} days")
    if not policy.cleanup_enabled or not modes:
        return (
            f"Protected: newest {policy.minimum_backups} per type • Automatic cleanup off"
        )
    rules = "; ".join(modes)
    return (
        f"Protected: newest {policy.minimum_backups} per type • Cleanup: {rules}"
    )


def update_backup_policy_controls(owner) -> None:
    backups_enabled = owner.chkBackupPolicyEnabled.isChecked()
    owner.wdgBackupPolicyOptions.setEnabled(backups_enabled)
    owner.btnBackupHistoryCreate.setEnabled(backups_enabled)
    owner.btnBackupHistoryRestorePoint.setEnabled(backups_enabled)
    cleanup_enabled = backups_enabled and owner.chkBackupPolicyCleanupEnabled.isChecked()
    owner.wdgBackupPolicyCleanupOptions.setEnabled(cleanup_enabled)
    rules_enabled = cleanup_enabled and (
        owner.chkBackupPolicyCleanupCount.isChecked()
        or owner.chkBackupPolicyCleanupAge.isChecked()
    )
    owner.spinBackupPolicyMinimum.setEnabled(rules_enabled)
    owner.spinBackupPolicyCount.setMinimum(owner.spinBackupPolicyMinimum.value())
    owner.spinBackupPolicyCount.setEnabled(
        cleanup_enabled and owner.chkBackupPolicyCleanupCount.isChecked()
    )
    owner.spinBackupPolicyAge.setEnabled(
        cleanup_enabled and owner.chkBackupPolicyCleanupAge.isChecked()
    )


def update_backup_policy_state(owner) -> None:
    if getattr(owner, "_backup_policy_loading", False):
        return
    policy = collect_backup_policy(owner)
    update_backup_policy_controls(owner)
    summary = backup_retention_explanation(policy)
    baseline = getattr(owner, "_backup_policy_baseline", None)
    dirty = baseline is not None and policy != baseline
    owner.boxBackupPolicy.set_summary(
        f"{summary} • Unsaved changes" if dirty else summary
    )
    owner._backup_policy_dirty = dirty
    owner.btnBackupPolicyDiscard.setEnabled(dirty)
    owner.btnBackupPolicyReview.setEnabled(dirty)
    owner.btnBackupPolicyApply.setEnabled(False)
    if dirty:
        owner.lblBackupPolicyState.setText(
            "Unsaved backup-policy changes. Review them before applying."
        )
        owner.lblBackupPolicyState.set_kind("warning")
        owner.lblBackupPolicyReview.clear()
        owner.lblBackupPolicyReview.hide()
    elif baseline is not None:
        owner.lblBackupPolicyState.setText("Backup policy is current.")
        owner.lblBackupPolicyState.set_kind("success")


def populate_backup_policy(owner, policy: BackupPolicy) -> None:
    owner._backup_policy_loading = True
    try:
        owner.chkBackupPolicyEnabled.setChecked(policy.enabled)
        owner.chkBackupStartupRecovery.setChecked(policy.startup_recovery_enabled)
        owner.chkBackupPolicyAutosave.setChecked(policy.on_autosave)
        owner.chkBackupPolicyCrash.setChecked(policy.on_crash_detect)
        owner.chkBackupPolicyShutdown.setChecked(policy.on_shutdown)
        owner.chkBackupPolicyCleanupEnabled.setChecked(policy.cleanup_enabled)
        owner.chkBackupPolicyCleanupCount.setChecked(policy.cleanup_by_count)
        owner.chkBackupPolicyCleanupAge.setChecked(policy.cleanup_by_age)
        owner.spinBackupPolicyMinimum.setValue(policy.minimum_backups)
        owner.spinBackupPolicyCount.setValue(policy.max_backups)
        owner.spinBackupPolicyAge.setValue(policy.max_age_days)
        owner._backup_policy_baseline = policy
    finally:
        owner._backup_policy_loading = False
    owner.lblBackupPolicyReview.clear()
    owner.lblBackupPolicyReview.hide()
    owner.btnBackupHistoryCreate.setEnabled(policy.enabled)
    owner.btnBackupHistoryRestorePoint.setEnabled(policy.enabled)
    update_backup_policy_state(owner)


def review_backup_policy(owner) -> None:
    policy = collect_backup_policy(owner)
    owner.lblBackupPolicyReview.setText(backup_policy_summary(policy))
    owner.lblBackupPolicyReview.set_kind("info")
    owner.lblBackupPolicyReview.show()
    owner.btnBackupPolicyApply.setEnabled(policy != owner._backup_policy_baseline)


def apply_backup_history_filter(owner) -> None:
    """Render the selected category from the cached read-only archive scan."""
    tree = owner.treeBackupHistory
    tree.clear()
    archives: Sequence[Mapping[str, Any]] = getattr(
        owner, "_backup_history_archives", []
    )
    error = str(getattr(owner, "_backup_history_error", "") or "")
    root = str(getattr(owner, "_backup_history_root", "") or "")
    category = str(owner.cmbBackupHistoryCategory.currentData() or "")
    pinned_only = owner.chkBackupHistoryPinnedOnly.isChecked()
    matches = [
        archive
        for archive in archives
        if (not category or str(archive.get("category") or "Root") == category)
        and (not pinned_only or bool(archive.get("pinned")))
    ]
    displayed = filter_backup_archives(
        archives, category, pinned_only=pinned_only
    )
    owner.lblBackupHistoryStatus.setToolTip(
        f"Backup root: {root}" if root else ""
    )

    if error:
        owner.lblBackupHistoryStatus.setText(f"Backup history could not be loaded: {error}")
        owner.lblBackupHistoryStatus.set_kind("error")
    elif archives:
        summary = backup_history_summary(archives)
        owner.lblBackupHistoryStatus.setText(
            f"{summary['count']} archive(s) • "
            f"{format_archive_size(summary['size_bytes'])} total • "
            f"{summary['categories']} categor{'y' if summary['categories'] == 1 else 'ies'} • "
            f"Newest: {summary['newest']} • Oldest: {summary['oldest']}"
        )
        owner.lblBackupHistoryStatus.set_kind("success")
    else:
        owner.lblBackupHistoryStatus.setText(
            f"No backup archives were found under {root}."
        )
        owner.lblBackupHistoryStatus.set_kind("warning")

    for archive in displayed:
        path = str(archive.get("path") or "")
        item = QtWidgets.QTreeWidgetItem(
            [
                str(archive.get("modified") or ""),
                str(archive.get("category") or ""),
                str(
                    archive.get("pin_label")
                    or ("Restore Point" if archive.get("pinned") else "")
                ),
                str(archive.get("filename") or ""),
                format_archive_size(int(archive.get("size_bytes") or 0)),
            ]
        )
        item.setData(0, QtCore.Qt.UserRole, path)
        item.setData(0, QtCore.Qt.UserRole + 1, dict(archive))
        item.setToolTip(2, str(archive.get("pin_note") or ""))
        item.setToolTip(3, path)
        tree.addTopLevelItem(item)
    for column in range(tree.columnCount()):
        tree.resizeColumnToContents(column)
    if error:
        owner.lblBackupHistoryFilterStatus.setText("")
    elif matches:
        scope = category or "all categories"
        if pinned_only:
            scope = f"restore points in {scope}"
        limited = len(matches) > len(displayed)
        message = (
            f"Showing the newest {len(displayed)} of {len(matches)} archive(s)"
            if limited
            else f"Showing all {len(matches)} archive(s)"
        )
        owner.lblBackupHistoryFilterStatus.setText(
            f"{message} in {scope}, newest first."
        )
    else:
        scope = category or "all categories"
        if pinned_only:
            scope = f"restore points in {scope}"
        owner.lblBackupHistoryFilterStatus.setText(
            f"No archives match {scope}."
        )
    owner.lblBackupHistoryPath.setText(
        "Select an archive to inspect its full path." if displayed else ""
    )


def populate_backup_history(owner, payload: Mapping[str, Any]) -> None:
    """Cache and render a backup history payload without filesystem work."""
    archives: Sequence[Mapping[str, Any]] = payload.get("archives") or []
    restore_status = payload.get("restore_status") or {}
    if restore_status.get("visible"):
        kind = str(restore_status.get("kind") or "warning")
        details = [
            str(restore_status.get("summary") or "Restore history needs attention."),
            str(restore_status.get("guidance") or ""),
        ]
        for label, key in (
            ("Safety backup", "safety_backup"),
            ("Recovery copy", "rollback_copy"),
            ("Journal", "journal"),
        ):
            value = str(restore_status.get(key) or "")
            if value:
                details.append(f"{label}: {value}")
        owner.lblRestoreRecoveryState.setText(
            "\n".join(item for item in details if item)
        )
        owner.lblRestoreRecoveryState.set_kind(
            "error" if kind == "error" else "info" if kind == "active" else "warning"
        )
        owner.lblRestoreRecoveryState.show()
    else:
        owner.lblRestoreRecoveryState.clear()
        owner.lblRestoreRecoveryState.hide()
    owner._backup_history_archives = list(archives)
    owner._backup_history_error = str(payload.get("error") or "")
    owner._backup_history_root = str(payload.get("root") or "")
    previous = str(owner.cmbBackupHistoryCategory.currentData() or "")
    categories = sorted(
        {str(archive.get("category") or "Root") for archive in archives},
        key=str.casefold,
    )
    owner.cmbBackupHistoryCategory.blockSignals(True)
    owner.cmbBackupHistoryCategory.clear()
    owner.cmbBackupHistoryCategory.addItem("All categories", "")
    for category in categories:
        owner.cmbBackupHistoryCategory.addItem(category, category)
    selected = owner.cmbBackupHistoryCategory.findData(previous)
    owner.cmbBackupHistoryCategory.setCurrentIndex(max(0, selected))
    owner.cmbBackupHistoryCategory.blockSignals(False)
    apply_backup_history_filter(owner)


def update_backup_history_selection(owner, current) -> None:
    """Show selected archive context and enable only applicable actions."""
    if current is None:
        owner.lblBackupHistoryPath.setText("Select an archive to inspect its details.")
        owner.btnBackupHistoryPin.setEnabled(False)
        owner.btnBackupHistoryPin.setText("Protect Selected")
        owner.btnBackupHistoryRemoveProtection.setVisible(False)
        owner.btnBackupHistoryPreview.setEnabled(False)
        return
    archive = current.data(0, QtCore.Qt.UserRole + 1) or {}
    path = str(current.data(0, QtCore.Qt.UserRole) or "")
    note = str(archive.get("pin_note") or "").strip()
    status = str(archive.get("pin_status") or "")
    details = path
    if note:
        details = f"{note}\n{path}"
    if status == "invalid":
        details = (
            "Restore-point metadata needs attention; cleanup protection remains active.\n"
            f"{details}"
        )
    owner.lblBackupHistoryPath.setText(details)
    pinned = bool(archive.get("pinned"))
    owner.btnBackupHistoryPin.setEnabled(True)
    owner.btnBackupHistoryPin.setText(
        "Edit Details" if pinned else "Protect Selected"
    )
    owner.btnBackupHistoryRemoveProtection.setVisible(pinned)
    owner.btnBackupHistoryRemoveProtection.setEnabled(pinned)
    owner.btnBackupHistoryPreview.setEnabled(
        not bool(getattr(owner, "_guarded_restore_running", False))
    )


def build_backup_history_view(owner) -> QtWidgets.QWidget:
    """Build the dedicated read-only Backups page."""
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.addWidget(
        PageHeader(
            "Backups",
            "Manage backup history, retention, restore points, and guarded save recovery.",
        )
    )
    layout.addWidget(
        InlineNotice(
            "Browsing never changes backup ZIPs. Protect Selected marks an existing "
            "backup as a restore point without copying it. Create from Current Save "
            "captures a new protected backup from the active save. Review and Restore "
            "validates the selected archive and requires a stopped server plus a "
            "verified, protected Before Restore safety point."
        )
    )
    owner.lblRestoreRecoveryState = InlineNotice()
    owner.lblRestoreRecoveryState.hide()
    layout.addWidget(owner.lblRestoreRecoveryState)

    owner._backup_policy_loading = False
    owner._backup_policy_baseline = None
    owner._backup_policy_dirty = False
    owner.boxBackupPolicy = CollapsibleBox("Backup Policy")
    owner.boxBackupPolicy.set_summary("Loading backup policy.")
    owner.lblBackupPolicyRetentionHelp = owner.boxBackupPolicy.summary
    policy_layout = owner.boxBackupPolicy.layout_for_rows()
    owner.chkBackupPolicyEnabled = QtWidgets.QCheckBox("Enable all save backups")
    master_font = owner.chkBackupPolicyEnabled.font()
    master_font.setBold(True)
    owner.chkBackupPolicyEnabled.setFont(master_font)
    policy_layout.addWidget(owner.chkBackupPolicyEnabled)
    master_help = QtWidgets.QLabel(
        "Master switch for save backups. When off, Backup Now and all automatic "
        "backup triggers are disabled. Existing backup archives and startup recovery "
        "are not affected."
    )
    master_help.setWordWrap(True)
    master_help.setProperty("fieldHelp", True)
    policy_layout.addWidget(master_help)

    owner.chkBackupStartupRecovery = QtWidgets.QCheckBox(
        "Recover a missing save before server startup"
    )
    recovery_font = owner.chkBackupStartupRecovery.font()
    recovery_font.setBold(True)
    owner.chkBackupStartupRecovery.setFont(recovery_font)
    policy_layout.addWidget(owner.chkBackupStartupRecovery)
    recovery_help = QtWidgets.QLabel(
        "When a configured live save is missing but prior save backups exist, restore "
        "the newest valid backup before any server process or monitor starts. Startup "
        "is blocked if those backups cannot be verified. A first startup with no prior "
        "save backups continues normally. Existing saves are never replaced."
    )
    recovery_help.setWordWrap(True)
    recovery_help.setProperty("fieldHelp", True)
    recovery_help.setContentsMargins(22, 0, 0, 4)
    policy_layout.addWidget(recovery_help)

    owner.wdgBackupPolicyOptions = QtWidgets.QWidget()
    policy_columns = QtWidgets.QHBoxLayout(owner.wdgBackupPolicyOptions)
    policy_columns.setContentsMargins(22, 4, 0, 0)
    policy_columns.setSpacing(SECTION_SPACING)

    owner.grpBackupPolicyTriggers = QtWidgets.QGroupBox("Automatic backups")
    trigger_layout = QtWidgets.QVBoxLayout(owner.grpBackupPolicyTriggers)
    trigger_intro = QtWidgets.QLabel(
        "Choose which detected server events create a save backup."
    )
    trigger_intro.setWordWrap(True)
    trigger_intro.setProperty("fieldHelp", True)
    trigger_layout.addWidget(trigger_intro)
    owner.chkBackupPolicyAutosave = QtWidgets.QCheckBox("After a server autosave")
    owner.chkBackupPolicyCrash = QtWidgets.QCheckBox("When a crash is detected")
    owner.chkBackupPolicyShutdown = QtWidgets.QCheckBox(
        "After a controlled shutdown"
    )
    trigger_layout.addWidget(owner.chkBackupPolicyAutosave)
    trigger_layout.addWidget(owner.chkBackupPolicyCrash)
    trigger_layout.addWidget(owner.chkBackupPolicyShutdown)
    trigger_help = QtWidgets.QLabel(
        "Autosave and crash changes take effect when the log monitor next starts. "
        "Startup and player login/logout backups are not available yet."
    )
    trigger_help.setWordWrap(True)
    trigger_help.setProperty("fieldHelp", True)
    trigger_layout.addWidget(trigger_help)
    trigger_layout.addStretch(1)

    owner.grpBackupPolicyRetention = QtWidgets.QGroupBox("Backup cleanup")
    retention_layout = QtWidgets.QVBoxLayout(owner.grpBackupPolicyRetention)
    owner.chkBackupPolicyCleanupEnabled = QtWidgets.QCheckBox(
        "Automatically remove old backup archives"
    )
    retention_intro = QtWidgets.QLabel(
        "Cleanup never changes the live server save."
    )
    retention_intro.setProperty("fieldHelp", True)
    cleanup_header = QtWidgets.QHBoxLayout()
    cleanup_header.addWidget(owner.chkBackupPolicyCleanupEnabled)
    cleanup_header.addSpacing(SECTION_SPACING)
    cleanup_header.addWidget(retention_intro)
    cleanup_header.addStretch(1)
    retention_layout.addLayout(cleanup_header)

    owner.wdgBackupPolicyCleanupOptions = QtWidgets.QWidget()
    owner.wdgBackupPolicyCleanupOptions.setMinimumHeight(100)
    cleanup_options = QtWidgets.QHBoxLayout(owner.wdgBackupPolicyCleanupOptions)
    cleanup_options.setContentsMargins(0, 0, 0, 0)
    cleanup_options.setSpacing(8)

    safety_card = QtWidgets.QFrame()
    safety_card.setProperty("policyOption", True)
    safety_layout = QtWidgets.QVBoxLayout(safety_card)
    safety_title = QtWidgets.QLabel("Protected backups")
    safety_title_font = safety_title.font()
    safety_title_font.setBold(True)
    safety_title.setFont(safety_title_font)
    safety_layout.addWidget(safety_title)
    minimum_row = QtWidgets.QHBoxLayout()
    owner.spinBackupPolicyMinimum = QtWidgets.QSpinBox()
    owner.spinBackupPolicyMinimum.setRange(1, 10000)
    owner.spinBackupPolicyMinimum.setFixedWidth(70)
    minimum_row.addWidget(owner.spinBackupPolicyMinimum)
    minimum_row.addWidget(QtWidgets.QLabel("minimum per type"))
    minimum_row.addStretch(1)
    safety_layout.addLayout(minimum_row)
    minimum_help = QtWidgets.QLabel(
        "Newest rollback points; never removed automatically."
    )
    minimum_help.setWordWrap(True)
    minimum_help.setProperty("fieldHelp", True)
    safety_layout.addWidget(minimum_help)

    count_card = QtWidgets.QFrame()
    count_card.setProperty("policyOption", True)
    count_layout = QtWidgets.QVBoxLayout(count_card)
    owner.chkBackupPolicyCleanupCount = QtWidgets.QCheckBox(
        "Count limit"
    )
    count_title_font = owner.chkBackupPolicyCleanupCount.font()
    count_title_font.setBold(True)
    owner.chkBackupPolicyCleanupCount.setFont(count_title_font)
    count_layout.addWidget(owner.chkBackupPolicyCleanupCount)
    owner.spinBackupPolicyCount = QtWidgets.QSpinBox()
    owner.spinBackupPolicyCount.setRange(1, 10000)
    owner.spinBackupPolicyCount.setFixedWidth(70)
    count_row = QtWidgets.QHBoxLayout()
    count_row.addWidget(owner.spinBackupPolicyCount)
    count_row.addWidget(QtWidgets.QLabel("maximum per type"))
    count_row.addStretch(1)
    count_layout.addLayout(count_row)
    count_help = QtWidgets.QLabel(
        "Removes oldest unprotected backups first."
    )
    count_help.setWordWrap(True)
    count_help.setProperty("fieldHelp", True)
    count_layout.addWidget(count_help)

    age_card = QtWidgets.QFrame()
    age_card.setProperty("policyOption", True)
    age_layout = QtWidgets.QVBoxLayout(age_card)
    owner.chkBackupPolicyCleanupAge = QtWidgets.QCheckBox(
        "Age limit"
    )
    age_title_font = owner.chkBackupPolicyCleanupAge.font()
    age_title_font.setBold(True)
    owner.chkBackupPolicyCleanupAge.setFont(age_title_font)
    age_layout.addWidget(owner.chkBackupPolicyCleanupAge)
    owner.spinBackupPolicyAge = QtWidgets.QSpinBox()
    owner.spinBackupPolicyAge.setRange(1, 3650)
    owner.spinBackupPolicyAge.setFixedWidth(70)
    age_row = QtWidgets.QHBoxLayout()
    age_row.addWidget(owner.spinBackupPolicyAge)
    age_row.addWidget(QtWidgets.QLabel("full days"))
    age_row.addStretch(1)
    age_layout.addLayout(age_row)
    age_help = QtWidgets.QLabel(
        "Removes only older, unprotected backups."
    )
    age_help.setWordWrap(True)
    age_help.setProperty("fieldHelp", True)
    age_layout.addWidget(age_help)

    cleanup_options.addWidget(safety_card, 1)
    cleanup_options.addWidget(count_card, 1)
    cleanup_options.addWidget(age_card, 1)
    retention_layout.addWidget(owner.wdgBackupPolicyCleanupOptions)
    retention_layout.addStretch(1)

    policy_columns.addWidget(owner.grpBackupPolicyTriggers, 2)
    policy_columns.addWidget(owner.grpBackupPolicyRetention, 3)
    policy_layout.addWidget(owner.wdgBackupPolicyOptions)
    owner.lblBackupPolicyState = InlineNotice("Loading backup policy.")
    owner.lblBackupPolicyReview = InlineNotice()
    owner.lblBackupPolicyReview.hide()
    policy_layout.addWidget(owner.lblBackupPolicyReview)
    policy_footer = QtWidgets.QHBoxLayout()
    owner.btnBackupPolicyDiscard = QtWidgets.QPushButton("Discard Changes")
    owner.btnBackupPolicyReview = QtWidgets.QPushButton("Review Changes")
    owner.btnBackupPolicyApply = QtWidgets.QPushButton("Apply Policy")
    for button in (
        owner.btnBackupPolicyDiscard,
        owner.btnBackupPolicyReview,
        owner.btnBackupPolicyApply,
    ):
        button.setEnabled(False)
    set_button_role(owner.btnBackupPolicyDiscard, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupPolicyReview, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupPolicyApply, BUTTON_PRIMARY)
    policy_footer.addWidget(owner.lblBackupPolicyState, 1)
    policy_footer.addWidget(owner.btnBackupPolicyDiscard)
    policy_footer.addWidget(owner.btnBackupPolicyReview)
    policy_footer.addWidget(owner.btnBackupPolicyApply)
    policy_layout.addLayout(policy_footer)
    layout.addWidget(owner.boxBackupPolicy)

    owner.grpBackupArchives = QtWidgets.QGroupBox("Backup Archives")
    archive_layout = QtWidgets.QVBoxLayout(owner.grpBackupArchives)
    archive_layout.setSpacing(CONTROL_SPACING)
    archive_intro = QtWidgets.QLabel(
        "Browse existing archives, create or protect rollback points, and safely restore a selected save backup."
    )
    archive_intro.setProperty("fieldHelp", True)

    owner.btnBackupHistoryRefresh = QtWidgets.QPushButton("Refresh")
    owner.btnBackupHistoryOpen = QtWidgets.QPushButton("Open Backups Folder")
    owner.btnBackupHistoryCreate = QtWidgets.QPushButton("Backup Now")
    owner.btnBackupHistoryRestorePoint = QtWidgets.QPushButton(
        "Create from Current Save"
    )
    owner.btnBackupHistoryRestorePoint.setToolTip(
        "Create a new backup ZIP from the current server save and protect it as a restore point."
    )
    owner.btnBackupHistoryPin = QtWidgets.QPushButton("Protect Selected")
    owner.btnBackupHistoryPin.setToolTip(
        "Make the selected existing backup a restore point without creating another ZIP."
    )
    owner.btnBackupHistoryPin.setEnabled(False)
    owner.btnBackupHistoryPreview = QtWidgets.QPushButton("Review and Restore")
    owner.btnBackupHistoryPreview.setToolTip(
        "Validate the selected archive, review its destination and safeguards, then optionally restore it."
    )
    owner.btnBackupHistoryPreview.setEnabled(False)
    owner.btnBackupHistoryRemoveProtection = QtWidgets.QPushButton(
        "Remove Protection"
    )
    owner.btnBackupHistoryRemoveProtection.setToolTip(
        "Keep the backup ZIP but allow automatic cleanup rules to remove it later."
    )
    owner.btnBackupHistoryRemoveProtection.setVisible(False)
    owner.cmbBackupHistoryCategory = QtWidgets.QComboBox()
    owner.cmbBackupHistoryCategory.addItem("All categories", "")
    owner.cmbBackupHistoryCategory.setMinimumWidth(180)
    set_button_role(owner.btnBackupHistoryRefresh, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryOpen, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryCreate, BUTTON_PRIMARY)
    set_button_role(owner.btnBackupHistoryRestorePoint, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryPin, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryPreview, BUTTON_PRIMARY)
    set_button_role(owner.btnBackupHistoryRemoveProtection, BUTTON_SECONDARY)

    archive_header = QtWidgets.QHBoxLayout()
    archive_header.addWidget(archive_intro, 1)
    archive_header.addWidget(owner.btnBackupHistoryCreate)
    archive_layout.addLayout(archive_header)

    controls = QtWidgets.QHBoxLayout()
    controls.addWidget(owner.btnBackupHistoryRefresh)
    controls.addWidget(owner.btnBackupHistoryOpen)
    controls.addSpacing(SECTION_SPACING)
    controls.addWidget(QtWidgets.QLabel("Show"))
    controls.addWidget(owner.cmbBackupHistoryCategory)
    owner.chkBackupHistoryPinnedOnly = QtWidgets.QCheckBox("Restore points only")
    controls.addWidget(owner.chkBackupHistoryPinnedOnly)
    controls.addStretch(1)
    archive_layout.addLayout(controls)

    restore_controls = QtWidgets.QHBoxLayout()
    owner.lblBackupSelectedActions = QtWidgets.QLabel("Selected backup:")
    owner.lblBackupSelectedActions.setProperty("fieldHelp", True)
    restore_controls.addWidget(owner.lblBackupSelectedActions)
    restore_controls.addWidget(owner.btnBackupHistoryPreview)
    restore_controls.addWidget(owner.btnBackupHistoryPin)
    restore_controls.addWidget(owner.btnBackupHistoryRemoveProtection)
    restore_controls.addStretch(1)
    owner.lblBackupNewRestorePoint = QtWidgets.QLabel("New restore point:")
    owner.lblBackupNewRestorePoint.setProperty("fieldHelp", True)
    restore_controls.addWidget(owner.lblBackupNewRestorePoint)
    restore_controls.addWidget(owner.btnBackupHistoryRestorePoint)
    archive_layout.addLayout(restore_controls)

    owner.lblBackupHistoryStatus = InlineNotice("Loading backup history.")
    archive_layout.addWidget(owner.lblBackupHistoryStatus)
    owner.lblBackupHistoryFilterStatus = QtWidgets.QLabel()
    owner.lblBackupHistoryFilterStatus.setProperty("fieldHelp", True)
    archive_layout.addWidget(owner.lblBackupHistoryFilterStatus)

    owner.treeBackupHistory = QtWidgets.QTreeWidget()
    owner.treeBackupHistory.setColumnCount(5)
    owner.treeBackupHistory.setHeaderLabels(
        ["Created", "Category", "Restore Point", "Archive", "Size"]
    )
    owner.treeBackupHistory.setRootIsDecorated(False)
    owner.treeBackupHistory.setAlternatingRowColors(True)
    owner.treeBackupHistory.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    owner.treeBackupHistory.setSortingEnabled(False)
    owner.treeBackupHistory.setMinimumHeight(200)
    archive_layout.addWidget(owner.treeBackupHistory, 1)

    owner.lblBackupHistoryPath = QtWidgets.QLabel()
    owner.lblBackupHistoryPath.setWordWrap(True)
    owner.lblBackupHistoryPath.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    archive_layout.addWidget(owner.lblBackupHistoryPath)
    layout.addWidget(owner.grpBackupArchives, 1)

    owner.treeBackupHistory.currentItemChanged.connect(
        lambda current, _previous: update_backup_history_selection(owner, current)
    )
    owner.cmbBackupHistoryCategory.currentIndexChanged.connect(
        lambda _index: apply_backup_history_filter(owner)
    )
    owner.chkBackupHistoryPinnedOnly.toggled.connect(
        lambda _checked: apply_backup_history_filter(owner)
    )
    owner.btnBackupHistoryRefresh.clicked.connect(
        getattr(owner, "_refresh_backup_history", lambda: None)
    )
    owner.btnBackupHistoryOpen.clicked.connect(
        getattr(owner, "_on_open_backups_clicked", lambda: None)
    )
    owner.btnBackupHistoryCreate.clicked.connect(
        getattr(owner, "_on_backup_now_clicked", lambda: None)
    )
    owner.btnBackupHistoryRestorePoint.clicked.connect(
        getattr(owner, "_on_create_restore_point_clicked", lambda: None)
    )
    owner.btnBackupHistoryPin.clicked.connect(
        getattr(owner, "_on_pin_backup_clicked", lambda: None)
    )
    owner.btnBackupHistoryPreview.clicked.connect(
        getattr(owner, "_on_preview_restore_clicked", lambda: None)
    )
    owner.btnBackupHistoryRemoveProtection.clicked.connect(
        getattr(owner, "_on_remove_restore_point_protection_clicked", lambda: None)
    )
    owner.btnBackupPolicyDiscard.clicked.connect(
        lambda: populate_backup_policy(owner, owner._backup_policy_baseline)
    )
    owner.btnBackupPolicyReview.clicked.connect(lambda: review_backup_policy(owner))
    owner.btnBackupPolicyApply.clicked.connect(
        getattr(owner, "_confirm_apply_backup_policy", lambda: None)
    )
    for field in (
        owner.chkBackupPolicyEnabled,
        owner.chkBackupStartupRecovery,
        owner.chkBackupPolicyAutosave,
        owner.chkBackupPolicyCrash,
        owner.chkBackupPolicyShutdown,
        owner.chkBackupPolicyCleanupEnabled,
        owner.chkBackupPolicyCleanupCount,
        owner.chkBackupPolicyCleanupAge,
        owner.spinBackupPolicyMinimum,
        owner.spinBackupPolicyCount,
        owner.spinBackupPolicyAge,
    ):
        signal = getattr(field, "valueChanged", None) or field.toggled
        signal.connect(lambda *_: update_backup_policy_state(owner))
    scroll.setWidget(widget)
    return scroll
