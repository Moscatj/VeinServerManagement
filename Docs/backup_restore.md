# Guarded Backup Restore

The Backups page exposes **Review and Restore** for explicit operator-driven save
rollback. Browsing and preview remain read-only; activation is available only
after validation passes and the operator accepts a final confirmation.

## Implemented Backend

`Controller/Tools/backup_restore.py` provides tested manual-restore and startup-
recovery paths that share archive validation, verified staging, operation locking,
and atomic activation.

The guarded manual engine:

1. Acquires an exclusive operation lock and writes a restore journal.
2. Requires the server to be stopped before preparation begins.
3. Revalidates the selected ZIP, safe member paths, manifest, and save hash.
4. Requires an existing live save in this phase so rollback can be guaranteed.
5. Copies and verifies a temporary rollback copy.
6. Calls the shared backup workflow to create a **Before Restore** archive,
   validates it, verifies that its save hash exactly matches the current live
   save, and pins it against automatic cleanup.
7. Extracts only the declared save into a temporary staging file and verifies
   its hash.
8. Checks the server state again immediately before activation.
9. Atomically replaces the live save and verifies the result.
10. Restores the prior live save automatically when post-write validation fails.

If automatic rollback itself cannot be verified, the journal records the pinned
safety archive and any preserved rollback copy for operator recovery.

## Missing-Save Startup Recovery

`Controller/start_server.py` runs recovery preflight before Steam update, monitor
startup, or game-process launch. The same entrypoint is used by crash-monitor
automatic restarts, so recovery applies to both operator and automatic starts.

When `backups.recovery.restore_missing_on_start` is enabled (the default):

1. Any existing configured save filename ends recovery immediately; automatic
   recovery never replaces it, including a zero-byte file.
2. With no live save and no prior `Server_*.zip` save archives, startup continues
   as a first-server start.
3. With prior save archives, candidates are checked newest-first. Unsafe,
   damaged, manifestless, wrong-name, empty, or hash-mismatched archives are
   rejected.
4. The newest valid candidate is staged, hash verified, and atomically installed
   only after a second authoritative server-process check.
5. If no candidate validates or activation cannot be verified, startup is
   blocked. The recovery journal is written under the configured runtime folder.

This restores the historical missing-save protection without guessing whether
an existing save is semantically corrupt. Future corruption detection requires a
reliable VEIN format or runtime health signal before it can safely authorize
automatic replacement.

## Invariants

- The selected backup ZIP is never modified or deleted.
- A live save is never replaced while the server is known to be running.
- No replacement occurs unless the selected archive and mandatory safety backup
  both pass validation.
- Temporary staging files are never treated as backup archives.
- Successful activation uses an atomic same-volume replacement.
- Automatic startup recovery creates only a missing save and never overwrites an
  existing one.
- Cleanup protection for the Before Restore archive is established before the
  live save is changed.
- Tests use temporary directories and injected backup/server-state helpers; they
  never touch a real Vein installation.

## GUI Workflow

- Select an archive and choose **Review and Restore**.
- The dialog repeats source, destination, validation, server state, safety-backup
  behavior, and the consequence that the selected save becomes active.
- Restore is unavailable unless the server is stopped, the current live save is
  present, the archive validates, and backup creation is enabled.
- On confirmation, lifecycle actions and Backup Policy edits are disabled while
  a background worker invokes the shared guarded engine.
- The engine rechecks authoritative process state, creates and pins the mandatory
  Before Restore archive through the normal backup workflow, and revalidates
  everything before atomic activation.
- Completion leaves the server stopped and refreshes archive history so the new
  safety point is visible.

The Backups page also reads the operation journal during archive refresh. Normal
completed history stays hidden to avoid clutter. Active work, safe pre-change
failure, verified rollback, interrupted phases, unreadable state, and failed
rollback are distinguished explicitly. Critical guidance identifies the journal,
protected safety archive, and preserved recovery copy while telling the operator
to keep the server stopped. The GUI never deletes or silently repairs those
artifacts.

- The legacy `restore_from_latest()` compatibility entrypoint remains callable,
  but direct extraction is disabled so it cannot bypass guarded restoration.
