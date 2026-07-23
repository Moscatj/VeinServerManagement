# Vein Server Management — config.yaml Reference

This document explains every key in the tracked `Config/config.example.yaml` template and the local `Config/config.yaml` runtime file. Copy the example to `Config/config.yaml` for local use; the local file is ignored by Git.

Note: Any path value may now be expressed relative to the management root (the folder that contains `Controller/` and `Config/`). Relative entries are resolved during config load, so packaged builds work no matter which drive or directory the suite is installed on.

Current scope: `Config/config.yaml` describes one active server profile. Multiple
Vein dedicated server installs can exist on the same computer, but the
management suite currently starts, monitors, backs up, and shuts down the one
server root selected in this config. Future multi-server support should add
named profiles with separate server roots, ports, saves/logs, runtime state,
backups, Discord routing, and Steam update settings.

## Setup Workflow State

The `setup` block records onboarding state separately from the presence of a
server executable. It is maintained by the installer and Setup UI; operators
normally should not edit it by hand.

- `setup.schema_version`: metadata schema version; currently `1`.
- `setup.completed`: true only after the selected server has completed guarded
  setup/import successfully.
- `setup.server_root`: normalized server root associated with that completion
  record.
- `setup.source`: provenance such as `installer_new`, `quick_start_new`, or
  `existing_import`.
- `setup.completed_at`: UTC completion timestamp, blank while incomplete.

This distinction lets SteamCMD install binaries first and still route the first
GUI launch into First Setup. A completed record with missing binaries routes to
repair guidance instead of being mistaken for a brand-new configuration.

---

## Top-level Paths

- server_dir  
  • Folder that contains the Vein server executables.  
  • Current: Server

- server_executables (list)  
  • Executable names to try in order when starting the server.  
  • Current: ["VeinServer-Win64-Test.exe", "VeinServer.exe"]

- runtime_dir  
  • Where runtime flags, PIDs, and state JSONs are written.  
  • Current: Runtime

- save_filenames (list)  
  • Candidate world-save file names in the resolved SaveGames directory.
  • Current: ["Server.vns", "Server.sav"]

- mgmt_log_dir  
  • Root folder for management-suite stdout/stderr logs (VeinManager, monitors, helpers).  
  • Current: Logs


- backup_root  
  • Root folder for all backup categories.  
  • Current: Backups

---

## Vein SaveGames

- save_games.override
  • Advanced override for the Vein-generated world-save directory.
  • Leave blank for the recommended automatic path:
    `<server root>/Vein/Saved/SaveGames`.
  • Backups and health checks use the same resolved directory.
  • Legacy `save_dir`, `paths.save_dir`, and `paths.saves_dir` values remain
    readable, but Quick Start migrates them to this single setting.

The installer derives SaveGames from Server root and does not ask novice users
to select Vein's internal data folders.

---

## Vein Game Log

- game_log.override
  • Advanced override for the Vein-generated log read by the management app.
  • Leave blank for the recommended automatic path:
    `<server root>/Vein/Saved/Logs/Vein.log`.
  • Server launch and log monitoring use the same resolved file.
  • Legacy `logs_dir` and `absolute_log_file` values remain readable, but Quick
    Start migrates them to this single setting.

The Vein Game Log is read-only to the management suite. It is separate from
app-owned Management Logs under `Logs/` and Runtime Status Data under
`Runtime/`.

---

## Management Logs

- management_logs.root  
  • Overrides `paths.mgmt_log_dir` for grouping stdout/stderr per subsystem.  
  • Current: Logs

- management_logs.layout  
  • Maps subsystem names (vein_manager, monitor_log, crash_monitor, etc.) to folders under the root.  
  • Current: {"vein_manager": "gui", "start_server": "controller/start_server", "monitor_log": "monitors/log_monitor", "crash_monitor": "monitors/crash_monitor", "http_api": "monitors/http_api"}

- management_logs.retention  
  • Controls how many live management log files are kept before moving the rest to Archive/.
  • Current: {"max_files": 6, "max_age_days": 14}

- management_logs.archive  
  • Destination and retention window for archived management logs.  
  • Current: {"enabled": true, "root": "Logs/Archive", "max_files": 150, "max_age_days": 90}

See [management_logs.md](management_logs.md) for the full layout, archive behavior, and CLI helpers.

---

## Server Launch & Networking

- map_path  
  • Map/URL args (e.g., “/Game/Vein/Maps/ChamplainValley?listen”). Empty uses server defaults.  
  • Current: "" (empty)

- max_players  
  • Player cap passed to the server.  
  • Current: 8

- extra_launch_args (list)  
  • Additional CLI args (e.g., -SteamSockets).  
  • Current: ["-SteamSockets"]

- headless_mode  
  • Whether to launch server without a visible window (Windows flags).  
  • Current: true

- show_monitor_window  
  • When true, monitors spawn in visible consoles.  
  • Current: false

- multi_home_ip  
  • IP address for MultiHome binding.  
  • Current: 0.0.0.0

- game_port  
  • Server port.  
  • Current: 7777

- query_port  
  • Steam query port.  
  • Current: 27015

- enable_query_port  
  • Toggle to pass query-port arg.  
  • Current: true

---

## Steam Update Settings

- steamcmd_path  
  • Path to SteamCMD executable.  
  • Current: SteamCMD/steamcmd.exe

- app_id  
  • Steam App ID for Vein server.  
  • Current: 2131400

- auto_update_on_start  
  • Run SteamCMD before launch.  
  • Current: false

- steam_update_validate  
  • Use `validate` during update.  
  • Current: true

- steam_update_beta / steam_update_beta_password  
  • Optional beta channel and password.  
  • Current: "" / ""

- steam_update_retries  
  • Retry attempts if SteamCMD fails.  
  • Current: 2

- steam_update_timeout_seconds  
  • Timeout for a single update run.  
  • Current: 900

---

## Backup Policy

The Backups page safely edits the primary structured settings below. It exposes
only triggers with implemented runtime detection. Startup and player
login/logout controls remain roadmap items.

- backups.enabled
  • Global gate for save backup creation.
  • Legacy `backups.enable` remains compatible.

- backups.triggers.on_autosave
  • Back up when the monitored game log reports an autosave.

- backups.triggers.on_crash_detect
  • Back up when the log monitor detects a configured crash signature.

- backups.triggers.shutdown
  • Back up during controlled shutdown. Boolean and `enabled`/`save_backup`
    object forms remain compatible.

- backups.retention.default.max_backups
  • Default maximum archive count per category.

- backups.retention.default.max_age_days
  • Default maximum archive age per category.

- backups.retention.default.enabled
  • Master gate for automatic archive cleanup. When false, no count- or
    age-based cleanup occurs.

- backups.retention.default.by_count
  • Enables the maximum archive count rule independently.

- backups.retention.default.by_age
  • Enables the maximum archive age rule independently.

- backups.retention.default.minimum_backups
  • Number of newest archives in each backup category that automatic cleanup
    must always preserve. Defaults to 3 and cannot exceed an enabled count limit.

Count and age cleanup can both be enabled, either can be used alone, or both
can be disabled. After a new backup is created, enabled rules are evaluated for
that backup category. The configured minimum newest archives are protected
first. Count cleanup then removes the oldest unprotected archives until the
category is within its limit. Age cleanup removes unprotected archives more
than the configured number of full days old. Applying policy in the GUI does
not immediately delete existing archives; cleanup occurs when that category
next creates a backup. Cleanup is reached only after successful backup creation,
so a failed new backup cannot trigger deletion of existing rollback points.
Autosave and Crash trigger changes take effect when the log monitor next starts.

- max_backups  
  • Max total backups to retain per category.  
  • Current: 10

- backup_max_age_days  
  • Prune backups older than this many days (per category).  
  • Current: 7

- backup_folders (object)  
  • Explicit subfolders for categories under `backup_root`.  
  • Current:  
    - Manual  → Backups/Manual
    - Startup → Backups/Startup
    - Autosave → Backups/Autosave
    - Crash   → Backups/Crash

- nightly_backup (object)  
  • Scheduled backup policy for an external job/cron.  
  • Keys:  
    - enable (bool) → false  
    - max_backups (int) → 14  
    - max_backup_age_days (int) → 30  
    - discord_notify (bool) → true

---

## Monitor & Crash Handling

- crash_monitor_interval_seconds  
  • Polling interval for crash monitor loop.  
  • Current: 60

- crash_monitor_idle_notify_minutes  
  • Repeat interval for idle notices when server is offline.  
  • Current: 15

  • Attempts/sleep when rotating logs that might be locked.  
  • Current: 3 / 1.0

- preboot_shutdown  
  • If a server is running on start, shut it down first (clean restart).  
  • Current: true

- backup_on_detect  
  • Back up saves when a running/stale instance is detected at start.  
  • Current: true

- shutdown_timeout_sec  
  • Graceful shutdown wait before force-kill.  
  • Current: 60

- pre_shutdown_warning_seconds  
  • Broadcast warning (Discord + console) before stop.  
  • Current: 30

- stale_flag_delay_sec  
  • Delay used when clearing stale runtime flags.  
  • Current: 1

- restart_throttle_seconds  
  • Cooldown to avoid restart thrash.  
  • Current: 120

- startup_quiet_seconds  
  • Quiet window right after launch; crash monitor won’t trigger restarts during this.  
  • Current: 120

- crash_snippet_lines  
  • Number of log lines to include when reporting a crash.  
  • Current: 200

- logout_backup_debounce_seconds  
  • Debounce window for logout-triggered backups.  
  • Current: 90

- autosave_backup_cooldown_seconds  
  • Debounce window for autosave-triggered backups.  
  • Current: 300

---

## Discord

- discord.webhooks.default
  • Management-suite App Notifications webhook for startup, shutdown, crash,
    backup, player, and monitor messages.
  • Accepts a literal Discord webhook URL or `ENV:NAME` indirection.
  • Quick Start can update this value without exposing the stored secret.
  • Legacy `discord_webhook` remains compatible and takes precedence when both
    forms are present.

- `Game.ini` `DiscordChatWebhookURL`
  • VEIN in-game chat integration; requires a literal Discord webhook URL.

- `Game.ini` `DiscordChatAdminWebhookURL`
  • VEIN admin report integration; requires a literal Discord webhook URL.

- features.enable_discord (bool)  
  • Global gate for any Discord sending.  
  • Current: true

---

## Feature Flags (features.*)

- enable_backups → false  
- enable_steam_update → false
- enable_crash_monitor → true  
- enable_log_monitor → true  
- log_monitor_auto_restart → true

- discord_monitor → true  
- discord_shutdown → true  
- discord_startup → true  
- discord_backups → true  
- discord_crash_monitor → true

- enable_autosave_backups → false  

These drive which subsystems run, and which categories are allowed to post to Discord.

---

## Log Monitor Block (monitor.*)

- monitor.enable → true  
- monitor.heartbeat_interval_seconds → 300  
- monitor.state_file → Runtime/server_state.json
- monitor.wait_for_server_start_seconds → 600  
- monitor.wait_for_log_appearance_seconds → 120  
- monitor.tail_poll_interval_ms → 500

### monitor.track (what to parse)
- startup, auth, join, character, disconnect, autosave, crash, heartbeat → all true

### monitor.backups
- on_player_logout → false  
- on_autosave → true

### monitor.notify (what to send to Discord)
- startup → true  
- joinable → true  
- auth → true  
- join → true  
- character → true  
- disconnect → true  
- autosave → false  
- crash → true  
- heartbeat → false  
- monitor_status → true

---

## Miscellaneous

- kill_ue_helpers_on_shutdown  
  • If true, will attempt to kill Unreal helper processes during shutdown.  
  • Current: true

---

## Used By (quick map)

- start_server.py → paths, executables, ports, Steam update, preboot_shutdown, startup_quiet_seconds  
- monitor_log.py → resolved Vein Game Log, monitor.* (track/notify/heartbeat), autosave backup policy
- crash_monitor.py → crash_monitor_interval_seconds, restart_throttle_seconds, startup_quiet_seconds  
- shutdown_server.py → pre_shutdown_warning_seconds, backup paths, quiet/throttle during stop  
- Controller/Tools/* → feature gates, backups, Discord channel gates
- vein_manager.py (GUI) → reads/writes most keys; shows/edits monitor + features

---

## Tips

- ENV indirection: set the REAL Discord URL in your environment as DISCORD_WEBHOOK_URL.  
- If you change `server_dir` or executable names, verify in the GUI preflight.  
- Leave `game_log.override` blank unless a nonstandard server layout requires a custom file.
- To avoid touching any Vein game files directly, the toolkit leaves Vein.log alone; use external tooling if you need log archival.
- If crash monitor flaps, increase `startup_quiet_seconds` and/or `restart_throttle_seconds`.
