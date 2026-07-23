# nightly_backup.py — Summary
**Vein Server Management Suite**

---

## Purpose
Runs one **Nightly** backup through the shared backup service. Save discovery,
ZIP creation, Discord notification, and retention remain centralized rather
than being reimplemented by the scheduler entrypoint.

---

## Behavior
1. Optionally validates the explicit `VEIN_CONFIG` for useful diagnostics.
2. Calls `Tools.backups.make_backup("Nightly")`; the backup layer resolves
   configuration, the save file, destination, notification, and retention.
3. Calls `prune_backups("Nightly")` after creation. The backup layer already
   prunes on creation, so this is a safe second pass.
4. Returns success for a completed backup or intentional `BackupSkip`, and exit
   code `2` for unexpected failures.

---

## Key Functions
- `main()` — Runs one Nightly backup cycle and returns an operator-friendly exit code.

**Shared modules used**
- `Tools.config_io.load_and_validate_config` for optional validation.
- `Tools.backups.make_backup`, `BackupSkip`, and `prune_backups` for backup behavior.

---

## Configuration Keys (from `config.yaml`)
- `backups.enabled`, `backups.root`, and optional `backups.folders.Nightly`
- optional `backups.retention.Nightly` count/age policy
- `nightly_backup` schedule metadata is available to launchers; the entrypoint
  itself delegates enable/skip decisions to the shared backup layer
- legacy/global retention keys are normalized by the config compatibility layer

**Discord**: messages post to the **backups** channel (honors your global Discord enable + channel gating in features).

---

## Side Effects / Files
- Ensures the configured Nightly destination exists.
- Writes a `*.zip` backup with timestamped name into the Nightly folder.
- Deletes old Nightly backups per Nightly retention policy without crossing the
  configured minimum-backup safety floor or deleting protected restore points.

---

## Integration Points
- **Controller/Tools/backups.py** owns save discovery, ZIP creation, Discord
  notifications, and reason-specific pruning.
- **Controller/Tools/paths.py** resolves the configured or derived SaveGames path.

---

## Exit Conditions
- Disabled backups, missing saves, and other intentional skips print the reason
  and return success.

---

## Best Practices
- Keep Nightly retention independent from global retention (this script already does a temporary override for cleanup).
- Ensure Discord webhooks are configured if you want remote visibility.
- Store Nightly in a different subfolder than `Startup`, `Autosave`, or `Crash` to keep policies separate.

---

## Scheduling (Windows Task Scheduler)
1. **Action**: Start a program
   - Program: `py` (or full Python path)
   - Arguments: `-3 "<path-to>\Controller\nightly_backup.py"`
   - Start in: `<repo-root>`
2. **Trigger**: Daily at a quiet time (e.g., 3:00 AM)
3. **Options**: Run task whether user is logged on or not

Packaged Task Scheduler jobs can call `VeinTools.exe nightly-backup`; source
jobs can call `python Controller\nightly_backup.py` from the repository root.

---

## Troubleshooting
- **“Save file missing”**: Verify the server root, derived `SaveGames` folder,
  advanced `save_games.override`, and `save_filenames` in `config.yaml`.
- **No zips created**: Check write permissions for `backup_root` and Nightly folder.
- **No Discord messages**: Verify global Discord enable, backups channel gating, and webhook environment/URL resolution.

---

_Audited against v2.9.0 on 2026-07-14._
