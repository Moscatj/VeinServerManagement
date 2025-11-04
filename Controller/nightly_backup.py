"""
nightly_backup.py
Creates a nightly backup of the server save and prunes old Nightly backups.

Behavior:
- Reads all settings from config.json:
    - backup_root
    - backup_folders.Nightly  (destination subfolder name)
    - nightly_backup.enable / max_backups / max_backup_age_days / discord_notify
- Uses utils.backup_save_file() for the actual zip creation
- Uses utils.cleanup_old_backups() for pruning (by count/age) scoped to the Nightly folder
- Sends an optional Discord notification

No hardcoded paths; all file ops are via config + utils.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from config_helper import config
from utils import (
    backup_save_file,
    cleanup_old_backups,
    send_discord_message,
    SAVE_FILE,
)

# ----------------------------
# Config (single source of truth)
# ----------------------------
BACKUP_ROOT = Path(config["backup_root"])
FOLDERS = config.get("backup_folders", {})
NIGHTLY_DIR = BACKUP_ROOT / FOLDERS.get("Nightly", "Nightly")

NIGHTLY_CFG = config.get("nightly_backup", {})
NIGHTLY_ENABLED = bool(NIGHTLY_CFG.get("enable", True))
NIGHTLY_MAX_BACKUPS = int(NIGHTLY_CFG.get("max_backups", 30))
NIGHTLY_MAX_AGE_DAYS = int(NIGHTLY_CFG.get("max_backup_age_days", 60))
DISCORD_NOTIFY = bool(NIGHTLY_CFG.get("discord_notify", True))


def nightly_backup() -> None:
    """Run one nightly backup cycle."""
    if not NIGHTLY_ENABLED:
        print("[NightlyBackup] Nightly backup disabled in config.")
        return

    print("[NightlyBackup] Starting nightly backup…")

    # Ensure save exists (supporting Server.vns / Server.sav based on your config)
    if not Path(SAVE_FILE).exists():
        msg = "[NightlyBackup] Save file missing. No backup created."
        print(msg)
        if DISCORD_NOTIFY:
            send_discord_message("⚠ Nightly backup skipped — save file missing.", channel="backups")
        return

    NIGHTLY_DIR.mkdir(parents=True, exist_ok=True)

    # Create the backup into the configured Nightly folder.
    # utils.backup_save_file() names the file with a timestamp and emits a Discord message (if enabled).
    zip_path = backup_save_file(SAVE_FILE, reason="Nightly", override_destination=NIGHTLY_DIR)
    if zip_path:
        print(f"[NightlyBackup] Backup complete: {zip_path.name}")
        if DISCORD_NOTIFY:
            send_discord_message(f"🌙 Nightly backup complete: `{zip_path.name}`", channel="backups")

    # Prune old backups in the Nightly folder according to the nightly policy.
    # We temporarily override the global retention values only for the duration of this prune.
    original_max = config.get("max_backups", None)
    original_age = config.get("backup_max_age_days", None)
    try:
        config["max_backups"] = NIGHTLY_MAX_BACKUPS
        config["backup_max_age_days"] = NIGHTLY_MAX_AGE_DAYS
        cleanup_old_backups(NIGHTLY_DIR)
    finally:
        if original_max is None:
            config.pop("max_backups", None)
        else:
            config["max_backups"] = original_max
        if original_age is None:
            config.pop("backup_max_age_days", None)
        else:
            config["backup_max_age_days"] = original_age

    print("[NightlyBackup] Done.")


if __name__ == "__main__":
    nightly_backup()
