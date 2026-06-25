# nightly_backup.py — Summary
**Vein Server Management Suite**

---

## Purpose
Creates a **Nightly** backup of the active Vein server save and prunes old Nightly backups by **count** and **age** using settings from `config.yaml`. It uses shared utilities for the actual zip creation, pruning, and Discord notifications—no hardcoded paths.

---

## Behavior (What it does)
1. Reads config values:
   - `backup_root`
   - `backup_folders.Nightly` (subfolder name under `backup_root`)
   - `nightly_backup.enable`
   - `nightly_backup.max_backups`
   - `nightly_backup.max_backup_age_days`
   - `nightly_backup.discord_notify`
2. Verifies the current save file exists (via `utils.SAVE_FILE`).
3. Ensures the Nightly folder exists.
4. Calls `utils.backup_save_file(..., reason="Nightly", override_destination=NightlyDir)` to create a timestamped zip.
5. Optionally sends Discord success/failure messages to the **backups** channel.
6. Temporarily overrides global retention (`max_backups`, `backup_max_age_days`) **just for Nightly cleanup**, then calls `utils.cleanup_old_backups(NightlyDir)`, and restores the original values.
7. Prints progress and exits.

---

## Key Functions
- `nightly_backup()` — Runs one full Nightly backup cycle (idempotent).

**Imports/Utilities used**
- `from config_helper import config` — live configuration dictionary
- `from utils import backup_save_file, cleanup_old_backups, send_discord_message, SAVE_FILE` — shared helpers
- `pathlib.Path` — safe path ops

---

## Configuration Keys (from `config.yaml`)
- `backup_root` (string)
- `backup_folders.Nightly` (string; default `"Nightly"` if missing)
- `nightly_backup.enable` (bool; default `True`)
- `nightly_backup.max_backups` (int; default `30`)
- `nightly_backup.max_backup_age_days` (int; default `60`)
- `nightly_backup.discord_notify` (bool; default `True`)

**Discord**: messages post to the **backups** channel (honors your global Discord enable + channel gating in features).

---

## Side Effects / Files
- Ensures `"<backup_root>/<Nightly>/"` exists.
- Writes a `*.zip` backup with timestamped name into the Nightly folder.
- Deletes old Nightly backups per Nightly retention policy.

---

## Integration Points
- **Controller/Tools/backups.py**
  - `backup_save_file()` — creates zip of `SAVE_FILE` into a destination folder
  - `cleanup_old_backups()` — prunes by count and age
  - `send_discord_message()` — optional completion/skip notifications
  - `SAVE_FILE` — resolved path to the current server save
- **config_helper.py** — supplies the loaded `config` dict

---

## Exit Conditions
- If `nightly_backup.enable` is `False`, prints a notice and exits.
- If `SAVE_FILE` does not exist, prints and optionally posts a Discord warning, then exits.

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

*(If you prefer .bat: make `Scripts\RunNightlyBackup.bat` that calls `env_setup.bat` then runs `py -3 Controller\nightly_backup.py`.)*

---

## Troubleshooting
- **“Save file missing”**: Verify `utils.SAVE_FILE` points to an existing file and that `save_dir`/`save_filenames` are set correctly in `config.yaml`.
- **No zips created**: Check write permissions for `backup_root` and Nightly folder.
- **No Discord messages**: Verify global Discord enable, backups channel gating, and webhook environment/URL resolution.

---

_Last updated by AI code analysis for the Vein Server Management project._
