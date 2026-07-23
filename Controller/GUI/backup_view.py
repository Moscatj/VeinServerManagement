"""Read-only backup history view and background archive discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from PySide6 import QtCore, QtWidgets

from Tools.backups import list_backup_archives
from Tools.backup_policy import (
    BackupPolicy,
    apply_backup_policy,
    backup_policy_summary,
    load_backup_policy,
)
from .design_system import (
    BUTTON_PRIMARY,
    BUTTON_SECONDARY,
    InlineNotice,
    PAGE_MARGIN,
    SECTION_SPACING,
    PageHeader,
    set_button_role,
)


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


class BackupHistorySignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


class BackupHistoryWorker(QtCore.QRunnable):
    """Scan a configured backup root without blocking the GUI thread."""

    def __init__(self, root: str | Path, *, limit: int = 200) -> None:
        super().__init__()
        self.root = Path(root)
        self.limit = limit
        self.signals = BackupHistorySignals()

    def run(self) -> None:
        try:
            archives = list_backup_archives(self.root, limit=self.limit)
            payload = {
                "ok": True,
                "root": str(self.root),
                "archives": [archive.as_dict() for archive in archives],
                "error": "",
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "root": str(self.root),
                "archives": [],
                "error": str(exc),
            }
        self.signals.ready.emit(payload)


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
        on_autosave=owner.chkBackupPolicyAutosave.isChecked(),
        on_crash_detect=owner.chkBackupPolicyCrash.isChecked(),
        on_shutdown=owner.chkBackupPolicyShutdown.isChecked(),
        cleanup_enabled=owner.chkBackupPolicyCleanupEnabled.isChecked(),
        cleanup_by_count=owner.chkBackupPolicyCleanupCount.isChecked(),
        cleanup_by_age=owner.chkBackupPolicyCleanupAge.isChecked(),
        max_backups=owner.spinBackupPolicyCount.value(),
        max_age_days=owner.spinBackupPolicyAge.value(),
    )


def backup_retention_explanation(policy: BackupPolicy) -> str:
    modes = []
    if policy.cleanup_by_count:
        modes.append(f"keep at most {policy.max_backups} archives per backup type")
    if policy.cleanup_by_age:
        modes.append(f"remove archives more than {policy.max_age_days} full days old")
    if not policy.cleanup_enabled or not modes:
        return (
            "Automatic cleanup is off. Existing backup archives are kept until you "
            "delete them manually or enable at least one cleanup rule."
        )
    rules = " and ".join(modes)
    return (
        f"Automatic cleanup will {rules}. It runs after that backup type creates a "
        "new archive. Apply Policy does not immediately delete existing archives."
    )


def update_backup_policy_controls(owner) -> None:
    backups_enabled = owner.chkBackupPolicyEnabled.isChecked()
    owner.wdgBackupPolicyOptions.setEnabled(backups_enabled)
    owner.btnBackupHistoryCreate.setEnabled(backups_enabled)
    cleanup_enabled = backups_enabled and owner.chkBackupPolicyCleanupEnabled.isChecked()
    owner.wdgBackupPolicyCleanupOptions.setEnabled(cleanup_enabled)
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
    owner.lblBackupPolicyRetentionHelp.setText(
        backup_retention_explanation(policy)
    )
    baseline = getattr(owner, "_backup_policy_baseline", None)
    dirty = baseline is not None and policy != baseline
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
        owner.chkBackupPolicyAutosave.setChecked(policy.on_autosave)
        owner.chkBackupPolicyCrash.setChecked(policy.on_crash_detect)
        owner.chkBackupPolicyShutdown.setChecked(policy.on_shutdown)
        owner.chkBackupPolicyCleanupEnabled.setChecked(policy.cleanup_enabled)
        owner.chkBackupPolicyCleanupCount.setChecked(policy.cleanup_by_count)
        owner.chkBackupPolicyCleanupAge.setChecked(policy.cleanup_by_age)
        owner.spinBackupPolicyCount.setValue(policy.max_backups)
        owner.spinBackupPolicyAge.setValue(policy.max_age_days)
        owner._backup_policy_baseline = policy
    finally:
        owner._backup_policy_loading = False
    owner.lblBackupPolicyReview.clear()
    owner.lblBackupPolicyReview.hide()
    owner.btnBackupHistoryCreate.setEnabled(policy.enabled)
    update_backup_policy_state(owner)


def review_backup_policy(owner) -> None:
    policy = collect_backup_policy(owner)
    owner.lblBackupPolicyReview.setText(backup_policy_summary(policy))
    owner.lblBackupPolicyReview.set_kind("info")
    owner.lblBackupPolicyReview.show()
    owner.btnBackupPolicyApply.setEnabled(policy != owner._backup_policy_baseline)


def populate_backup_history(owner, payload: Mapping[str, Any]) -> None:
    """Render a backup history payload without performing filesystem work."""
    tree = owner.treeBackupHistory
    tree.clear()
    archives: Sequence[Mapping[str, Any]] = payload.get("archives") or []
    error = str(payload.get("error") or "")
    root = str(payload.get("root") or "")
    if error:
        owner.lblBackupHistoryStatus.setText(f"Backup history could not be loaded: {error}")
        owner.lblBackupHistoryStatus.set_kind("error")
    elif archives:
        owner.lblBackupHistoryStatus.setText(
            f"Showing {len(archives)} newest archive(s) under {root}."
        )
        owner.lblBackupHistoryStatus.set_kind("success")
    else:
        owner.lblBackupHistoryStatus.setText(
            f"No backup archives were found under {root}."
        )
        owner.lblBackupHistoryStatus.set_kind("warning")

    for archive in archives:
        path = str(archive.get("path") or "")
        item = QtWidgets.QTreeWidgetItem(
            [
                str(archive.get("modified") or ""),
                str(archive.get("category") or ""),
                str(archive.get("filename") or ""),
                format_archive_size(int(archive.get("size_bytes") or 0)),
            ]
        )
        item.setData(0, QtCore.Qt.UserRole, path)
        item.setToolTip(2, path)
        tree.addTopLevelItem(item)
    for column in range(tree.columnCount()):
        tree.resizeColumnToContents(column)
    owner.lblBackupHistoryPath.setText(
        "Select an archive to inspect its full path." if archives else ""
    )


def build_backup_history_view(owner) -> QtWidgets.QWidget:
    """Build the dedicated read-only Backups page."""
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    layout.setSpacing(SECTION_SPACING)
    layout.addWidget(
        PageHeader(
            "Backups",
            "Review save, log, and configuration archives without modifying them.",
        )
    )
    layout.addWidget(
        InlineNotice(
            "Archive browsing is read-only. Backup Now uses the same safe manual-backup "
            "workflow as Home. Loading a save is not offered until it can preview the "
            "destination, protect the current save, and validate the result."
        )
    )

    owner._backup_policy_loading = False
    owner._backup_policy_baseline = None
    owner._backup_policy_dirty = False
    policy_group = QtWidgets.QGroupBox("Backup Policy")
    policy_layout = QtWidgets.QVBoxLayout(policy_group)
    owner.chkBackupPolicyEnabled = QtWidgets.QCheckBox("Enable all save backups")
    master_font = owner.chkBackupPolicyEnabled.font()
    master_font.setBold(True)
    owner.chkBackupPolicyEnabled.setFont(master_font)
    policy_layout.addWidget(owner.chkBackupPolicyEnabled)
    master_help = QtWidgets.QLabel(
        "Master switch for save backups. When off, Backup Now and all automatic "
        "backup triggers are disabled. Existing backup archives are not deleted."
    )
    master_help.setWordWrap(True)
    master_help.setProperty("fieldHelp", True)
    policy_layout.addWidget(master_help)

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

    owner.grpBackupPolicyRetention = QtWidgets.QGroupBox(
        "Automatic cleanup"
    )
    retention_layout = QtWidgets.QVBoxLayout(owner.grpBackupPolicyRetention)
    owner.chkBackupPolicyCleanupEnabled = QtWidgets.QCheckBox(
        "Automatically remove old backup archives"
    )
    retention_layout.addWidget(owner.chkBackupPolicyCleanupEnabled)
    retention_intro = QtWidgets.QLabel(
        "Cleanup only removes backup ZIP archives. It never changes the live server save."
    )
    retention_intro.setWordWrap(True)
    retention_intro.setProperty("fieldHelp", True)
    retention_layout.addWidget(retention_intro)

    owner.wdgBackupPolicyCleanupOptions = QtWidgets.QWidget()
    cleanup_options = QtWidgets.QVBoxLayout(owner.wdgBackupPolicyCleanupOptions)
    cleanup_options.setContentsMargins(18, 0, 0, 0)
    cleanup_options.setSpacing(6)
    owner.chkBackupPolicyCleanupCount = QtWidgets.QCheckBox(
        "Limit the number kept per backup type"
    )
    owner.spinBackupPolicyCount = QtWidgets.QSpinBox()
    owner.spinBackupPolicyCount.setRange(1, 10000)
    owner.spinBackupPolicyCount.setSuffix(" backups")
    owner.spinBackupPolicyCount.setMinimumWidth(140)
    count_row = QtWidgets.QHBoxLayout()
    count_row.addWidget(owner.chkBackupPolicyCleanupCount)
    count_row.addStretch(1)
    count_row.addWidget(owner.spinBackupPolicyCount)
    cleanup_options.addLayout(count_row)
    count_help = QtWidgets.QLabel(
        "Oldest archives are removed first when this limit is exceeded."
    )
    count_help.setWordWrap(True)
    count_help.setProperty("fieldHelp", True)
    cleanup_options.addWidget(count_help)

    owner.chkBackupPolicyCleanupAge = QtWidgets.QCheckBox(
        "Remove backups older than"
    )
    owner.spinBackupPolicyAge = QtWidgets.QSpinBox()
    owner.spinBackupPolicyAge.setRange(1, 3650)
    owner.spinBackupPolicyAge.setSuffix(" days")
    owner.spinBackupPolicyAge.setMinimumWidth(140)
    age_row = QtWidgets.QHBoxLayout()
    age_row.addWidget(owner.chkBackupPolicyCleanupAge)
    age_row.addStretch(1)
    age_row.addWidget(owner.spinBackupPolicyAge)
    cleanup_options.addLayout(age_row)
    age_help = QtWidgets.QLabel(
        "Age is measured in full days when that backup type next runs cleanup."
    )
    age_help.setWordWrap(True)
    age_help.setProperty("fieldHelp", True)
    cleanup_options.addWidget(age_help)
    retention_layout.addWidget(owner.wdgBackupPolicyCleanupOptions)
    owner.lblBackupPolicyRetentionHelp = InlineNotice(
        backup_retention_explanation(BackupPolicy())
    )
    retention_layout.addWidget(owner.lblBackupPolicyRetentionHelp)
    retention_layout.addStretch(1)

    policy_columns.addWidget(owner.grpBackupPolicyTriggers, 1)
    policy_columns.addWidget(owner.grpBackupPolicyRetention, 1)
    policy_layout.addWidget(owner.wdgBackupPolicyOptions)
    owner.lblBackupPolicyState = InlineNotice("Loading backup policy.")
    owner.lblBackupPolicyReview = InlineNotice()
    owner.lblBackupPolicyReview.hide()
    policy_layout.addWidget(owner.lblBackupPolicyState)
    policy_layout.addWidget(owner.lblBackupPolicyReview)
    policy_actions = QtWidgets.QHBoxLayout()
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
    policy_actions.addWidget(owner.btnBackupPolicyDiscard)
    policy_actions.addStretch(1)
    policy_actions.addWidget(owner.btnBackupPolicyReview)
    policy_actions.addWidget(owner.btnBackupPolicyApply)
    policy_layout.addLayout(policy_actions)
    layout.addWidget(policy_group)

    controls = QtWidgets.QHBoxLayout()
    owner.btnBackupHistoryRefresh = QtWidgets.QPushButton("Refresh")
    owner.btnBackupHistoryOpen = QtWidgets.QPushButton("Open Backups Folder")
    owner.btnBackupHistoryCreate = QtWidgets.QPushButton("Backup Now")
    set_button_role(owner.btnBackupHistoryRefresh, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryOpen, BUTTON_SECONDARY)
    set_button_role(owner.btnBackupHistoryCreate, BUTTON_PRIMARY)
    controls.addWidget(owner.btnBackupHistoryRefresh)
    controls.addWidget(owner.btnBackupHistoryOpen)
    controls.addStretch(1)
    controls.addWidget(owner.btnBackupHistoryCreate)
    layout.addLayout(controls)

    owner.lblBackupHistoryStatus = InlineNotice("Loading backup history.")
    layout.addWidget(owner.lblBackupHistoryStatus)

    owner.treeBackupHistory = QtWidgets.QTreeWidget()
    owner.treeBackupHistory.setColumnCount(4)
    owner.treeBackupHistory.setHeaderLabels(["Created", "Category", "Archive", "Size"])
    owner.treeBackupHistory.setRootIsDecorated(False)
    owner.treeBackupHistory.setAlternatingRowColors(True)
    owner.treeBackupHistory.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    owner.treeBackupHistory.setSortingEnabled(False)
    layout.addWidget(owner.treeBackupHistory, 1)

    owner.lblBackupHistoryPath = QtWidgets.QLabel()
    owner.lblBackupHistoryPath.setWordWrap(True)
    owner.lblBackupHistoryPath.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    layout.addWidget(owner.lblBackupHistoryPath)

    owner.treeBackupHistory.currentItemChanged.connect(
        lambda current, _previous: owner.lblBackupHistoryPath.setText(
            str(current.data(0, QtCore.Qt.UserRole)) if current else ""
        )
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
    owner.btnBackupPolicyDiscard.clicked.connect(
        lambda: populate_backup_policy(owner, owner._backup_policy_baseline)
    )
    owner.btnBackupPolicyReview.clicked.connect(lambda: review_backup_policy(owner))
    owner.btnBackupPolicyApply.clicked.connect(
        getattr(owner, "_confirm_apply_backup_policy", lambda: None)
    )
    for field in (
        owner.chkBackupPolicyEnabled,
        owner.chkBackupPolicyAutosave,
        owner.chkBackupPolicyCrash,
        owner.chkBackupPolicyShutdown,
        owner.chkBackupPolicyCleanupEnabled,
        owner.chkBackupPolicyCleanupCount,
        owner.chkBackupPolicyCleanupAge,
        owner.spinBackupPolicyCount,
        owner.spinBackupPolicyAge,
    ):
        signal = getattr(field, "valueChanged", None) or field.toggled
        signal.connect(lambda *_: update_backup_policy_state(owner))
    return widget
