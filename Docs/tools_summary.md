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
- **monitors.py** - Convenience helpers for stopping log/crash monitors.
- **health_check.py** - Read-only project, dependency, path, SteamCMD, secret, and server-config diagnostics.
- **server_config_validator.py** - Read-only Vein dedicated server layout and `Game.ini` / `Engine.ini` validation.
- **server_quickstart.py** - Preview-only first-run setup planner for management config updates and guarded server config edits.
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

_Last updated after adding the Server Quick Start backend planner._
