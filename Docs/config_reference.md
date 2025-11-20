# Vein Server Management — config.json Reference

This document explains every key in `Config/config.json`, the source of truth for paths, feature toggles, ports, monitors, backups, and Discord. Values shown below reflect your current file.

Note: Any path value may now be expressed relative to the management root (the folder that contains `Controller/` and `Config/`). Relative entries are resolved during config load, so packaged builds work no matter which drive or directory the suite is installed on.

---

## Top-level Paths

- server_dir  
  • Folder that contains the Vein server executables.  
  • Current: G:/Servers/VeinServer

- server_executables (list)  
  • Executable names to try in order when starting the server.  
  • Current: ["VeinServer.exe", "VeinServer-Win64-Test.exe"]

- runtime_dir  
  • Where runtime flags, PIDs, and state JSONs are written.  
  • Current: G:/Servers/VeinServer/VeinServerManagement/Runtime

- save_dir  
  • Game save directory used for backup/restore.  
  • Current: G:/Servers/VeinServer/Vein/Saved/SaveGames

- save_filenames (list)  
  • Candidate save file names in `save_dir`.  
  • Current: ["Server.vns", "Server.sav"]

- logs_dir  
  • Directory where Vein writes rolling logs.  
  • Current: G:/Servers/VeinServer/Vein/Saved/Logs

- absolute_log_file  
  • If set, the log monitor tails this specific file instead of auto-picking the newest log.  
  • Current: G:/Servers/VeinServer/Vein/Saved/Logs/Vein.log
- mgmt_log_dir  
  • Root folder for management-suite stdout/stderr logs (VeinManager, monitors, helpers).  
  • Current: G:/Servers/VeinServer/VeinServerManagement/Logs


- backup_root  
  • Root folder for all backup categories.  
  • Current: G:/Servers/VeinServer/VeinServerManagement/Backups

---

## Management Logs

- management_logs.root  
  • Overrides `paths.mgmt_log_dir` for grouping stdout/stderr per subsystem.  
  • Current: G:/Servers/VeinServer/VeinServerManagement/Logs

- management_logs.layout  
  • Maps subsystem names (vein_manager, monitor_log, crash_monitor, etc.) to folders under the root.  
  • Current: {"vein_manager": "gui", "start_server": "controller/start_server", "monitor_log": "monitors/log_monitor", "crash_monitor": "monitors/crash_monitor", "http_api": "monitors/http_api"}

- management_logs.retention  
  • Controls how many live log files are kept before moving the rest to Archive/.  
  • Current: {"max_files": 6, "max_age_days": 14}

- management_logs.archive  
  • Destination and retention window for archived management logs.  
  • Current: {"enabled": true, "root": "G:/Servers/VeinServer/VeinServerManagement/Logs/Archive", "max_files": 150, "max_age_days": 90}

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
  • Current: C:/SteamCMD/steamcmd.exe

- app_id  
  • Steam App ID for Vein server.  
  • Current: 2131400

- auto_update_on_start  
  • Run SteamCMD before launch.  
  • Current: true

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

- max_backups  
  • Max total backups to retain per category.  
  • Current: 10

- backup_max_age_days  
  • Prune backups older than this many days (per category).  
  • Current: 7

- backup_folders (object)  
  • Explicit subfolders for categories under `backup_root`.  
  • Current:  
    - Manual  → G:/Servers/VeinServer/VeinServerManagement/Backups/Manual  
    - Startup → G:/Servers/VeinServer/VeinServerManagement/Backups/Startup  
    - Autosave → G:/Servers/VeinServer/VeinServerManagement/Backups/Autosave  
    - Crash   → G:/Servers/VeinServer/VeinServerManagement/Backups/Crash

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

- discord_webhook  
  • Webhook string or ENV indirection. If value begins with `ENV:NAME`, the actual URL is taken from that env var.  
  • Current: ENV:DISCORD_WEBHOOK_URL

- features.enable_discord (bool)  
  • Global gate for any Discord sending.  
  • Current: true

---

## Feature Flags (features.*)

- enable_backups → false  
- enable_steam_update → true  
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
- monitor.state_file → G:/Servers/VeinServer/VeinServerManagement/Runtime/server_state.json  
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
- monitor_log.py → logs_dir / absolute_log_file, monitor.* (track/notify/heartbeat), autosave backup policy  
- crash_monitor.py → crash_monitor_interval_seconds, restart_throttle_seconds, startup_quiet_seconds  
- shutdown_server.py → pre_shutdown_warning_seconds, backup paths, quiet/throttle during stop  
- Controller/Tools/* → feature gates, backups, Discord channel gates
- vein_manager.py (GUI) → reads/writes most keys; shows/edits monitor + features

---

## Tips

- ENV indirection: set the REAL Discord URL in your environment as DISCORD_WEBHOOK_URL.  
- If you change `server_dir` or executable names, verify in the GUI preflight.  
- Keep `absolute_log_file` set to the main log for most stable tailing.  
- To avoid touching any Vein game files directly, the toolkit leaves Vein.log alone; use external tooling if you need log archival.
- If crash monitor flaps, increase `startup_quiet_seconds` and/or `restart_throttle_seconds`.
