# Tools Modules Summary - Vein Server Management Suite

The legacy monolithic `utils.py` module has been decomposed into focused helpers
under `Controller/Tools/`. Each module has a single responsibility, which makes
the controller scripts easier to understand and test. `Controller/utils.py` has
been deleted permanently; do not recreate or patch it. All future shared logic
must live in the appropriate Tools module.

---

## Key Modules

- **process.py** - Process discovery, launch, shutdown, and Steam executable selection.
- **runtime.py** - Runtime flag management (`server_running.flag`, startup/shutdown locks, state writers).
- **restart.py** - Controlled restart orchestration used by the crash monitor.
- **features.py** - Centralized feature gating (`is_feature_enabled`).
- **paths.py** - Normalized server/log/save paths plus `resolve_save_file()`.
- **config_summary.py** - Human-readable config summaries for preflight diagnostics.
- **update_steam.py** - `check_for_steam_update()` and CLI wrapper around SteamCMD.
- **backups.py / backups_api.py** - Backup plumbing plus a safe API for controllers/GUI.
- **backup_policy.py** - Guarded backup-policy loading, summary, config backup,
  atomic write, and post-write validation for the Backups page.
- **backup_pins.py** - Atomic sidecar metadata for labeled restore points,
  editable details, guarded protection removal, and fail-safe cleanup protection
  without modifying backup ZIPs.
- **backup_restore_preview.py** - Read-only ZIP, manifest, save-hash,
  destination, and server-state assessment used by guarded restore.
- **backup_restore.py** - Guarded manual restore and missing-save startup recovery
  with locking, journaling, mandatory pinned safety backup where a live save
  exists, verified staging, atomic activation, and read-only recovery-state
  assessment for operator guidance,
  and automatic rollback.
- **monitors.py** - Convenience helpers for stopping log/crash monitors.
- **health_check.py** - Read-only project, dependency, path, SteamCMD, secret, and server-config diagnostics.
- **server_config_validator.py** - Read-only Vein dedicated server layout and `Game.ini` / `Engine.ini` validation.
- **server_config_preview.py / server_config_editor.py** - Secret-masked INI
  previews plus allowlisted edits with backup, atomic write, and validation.
- **server_quickstart.py** - Guarded New Server and Existing Server setup planning, validation, importing, and apply helpers.
- **steamcmd_runner.py** - Packaged SteamCMD execution with progress parsing,
  initialization, retry support, and installer-facing status.
- **mgmt_logs.py / log_search.py** - Management-log allocation, retention,
  archive, search, and error-summary support.
- **uninstall_cleanup.py** - Best-effort controlled process cleanup invoked by
  the Windows uninstaller.
- **app_info.py** - Installed/source version and runtime details for About.
- **architecture_check.py** - Subsystem-registry validation plus guardrails for
  reverse source/test/infrastructure ownership, removed modules, production
  absolute paths, GUI process termination, and guarded server-config writer
  ownership. Its `--route` mode reports the risk, focused tests, documentation,
  and invariants for one or more affected paths.
- **documentation_check.py** - CI and pre-release validation for changelog,
  release-tag, current-version declaration, generic version-example, and
  relative Markdown-link consistency.
- **source_hygiene_check.py** - Reusable local/CI scan for likely secrets,
  private local markers, and unsafe external scan targets.
- **discord.py** - Webhook utilities (`send_discord_message`, per-channel gating).
- **state_io.py** - Atomic state/heartbeat writers shared by monitors and the GUI.

Other helper modules such as `log_events.py`, `steam_version.py`,
`config_io.py`, and `vein_http_api.py` remain focused support modules.

---

## Migration Notes

- Any imports that previously referenced `utils` should now point directly to the relevant `Tools` module.
- Shutdown and monitor scripts should import `send_discord_message` from `Tools.discord` and process helpers from `Tools.process`.
- Backup consumers should use `Tools.backups_api` instead of the old `utils.backup_save_file()` shim.
- New shared behavior belongs under `Controller/Tools/`, not in a recreated compatibility module.

This decomposition makes it clear which module provides which behavior and prevents a single file from becoming a bottleneck for future changes.

---

_Audited against v2.9.0 on 2026-07-14._
