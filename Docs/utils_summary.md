# utils.py Summary — Vein Server Management Suite

## Overview
`utils.py` is the central shared helper module for the Vein Dedicated Server
Management Suite. It provides **process control**, **backup handling**, **SteamCMD
updates**, **Discord notifications**, **log rotation**, and **config-driven state
management** for both the CLI tools and GUI (vein_manager.py).

All paths, ports, and feature toggles are derived from `config.json` via
`config_helper`. No hardcoded directories or credentials exist. The module
strives to be crash-resilient and lightweight, keeping all retries and sleeps
conservative to minimize CPU and I/O usage.

---

## Primary Responsibilities
- **Process lifecycle control**
  - Discover, start, stop, and restart the Vein dedicated server process.
  - Manage coordination flags in `Runtime/` (`server_running.flag`,
    `startup_in_progress.lock`, etc.).
  - Detect existing instances, perform graceful shutdowns, and issue
    forced kills when necessary.
- **Backup management**
  - Create timestamped ZIP archives of game saves.
  - Retain or prune backups based on config values for max count and age.
  - Automatically restore missing save files from the newest backup.
- **SteamCMD updates**
  - Optionally run `steamcmd.exe` updates for the configured App ID.
  - Supports beta channels, validation, and retry logic.
  - Reports success/failure to Discord.
- **Discord notifications**
  - Send webhook messages for server startup, crash, backup, and update
    events.
  - Respects global and per-channel enable flags.
  - Uses safe length limits and gracefully degrades if the `requests`
    library is unavailable.
- **Log rotation**
  - Optionally rotate and compress `Vein.log` on demand or at startup.
  - Handles locked files via copy-truncate fallback.
- **Crash and monitor orchestration**
  - Provide helpers to stop the crash or log monitor processes.
  - Handle quiet windows and throttle logic to prevent rapid restart loops.
- **Configuration summaries**
  - Expose `summarize_config()` for preflight reporting and diagnostics.

---

## Function Map (abridged)

| Category | Key Functions | Description / Notes |
|-----------|---------------|--------------------|
| **Flag Management** | `write_flag`, `read_flag`, `clear_flag`, `begin_intentional_shutdown`, `is_shutdown_in_progress` | Maintain authoritative runtime and shutdown state flags in `Runtime/`. |
| **Process Control** | `find_running_server`, `stop_vein_server`, `stop_all_vein_processes_aggressive`, `kill_process_tree`, `start_vein_server`, `is_server_running` | Find, terminate, or launch server processes. Use `psutil` and `taskkill` for resilience. |
| **Monitors** | `stop_log_monitor`, `stop_crash_monitor`, `stop_all_monitors` | Terminate monitoring subprocesses cleanly. |
| **Backups** | `backup_save_file`, `cleanup_old_backups`, `auto_restore_save_file` | Create, prune, and restore save backups (ZIP-based). Posts to Discord on success/failure. |
| **Steam Updates** | `check_for_steam_update` | Run SteamCMD updates with retries and optional validation; Discord integration included. |
| **Logs** | `rotate_log_file`, `rotate_server_log` | Rotate current log file, zip, and prune old copies. |
| **Orchestration** | `initiate_controlled_restart`, `set_autorestart_quiet_period`, `startup_grace_active` | Manage restarts, throttle windows, and startup grace periods. |
| **Config Summary** | `summarize_config`, `resolve_server_executable` | Produce structured summary of config and resolved paths/executables. |
| **Discord** | `send_discord_message`, `_discord_webhook_url` | Safe Discord webhook posting for startup, crash, backup, and update notifications. |

---

## Integration Points
- **`start_server.py`** → uses `start_vein_server()` and flag helpers.
- **`monitor_log.py`** → uses log and Discord helpers to broadcast player and event data.
- **`crash_monitor.py`** → calls process restart and flag utilities.
- **`vein_manager.py` (GUI)** → reads and writes config values, calls server start/stop helpers, and displays logs.
- **`config_helper.py`** → provides runtime paths, toggles, and feature gates consumed here.

---

## Key Paths & Flags
| Purpose | Path / File | Description |
|----------|--------------|-------------|
| Server state | `Runtime/server_running.flag` | JSON data with PID, executable, and map. |
| Startup lock | `Runtime/startup_in_progress.lock` | Prevents false crash triggers during boot. |
| Shutdown marker | `Runtime/shutdown_in_progress.flag` | Signals intentional shutdown. |
| Restart throttle | `Runtime/last_restart_at.txt` | Limits restart frequency. |

---

## Discord Integration
Discord webhooks provide real-time visibility of server activity to admins and players:
- Player logins/logouts (from `monitor_log.py`)
- Server start/stop messages
- Crash detection and recovery alerts
- Backup creation or failure messages
- Steam update status

Messages are concise, timestamped, and channel-filtered (`startup`, `crash`, `backups`, etc.).

---

## Notes & Best Practices
- **No hardcoded paths** — all paths resolved via `config.json` keys.
- **Windows-specific behavior** — uses `taskkill` and PowerShell commands.
- **Error resilience** — all I/O wrapped in try/except; no silent infinite loops.
- **Crash safety** — respects quiet and startup grace periods before restarts.
- **Discord fallback** — continues operation even if webhooks or `requests` fail.

---

_Last updated automatically by AI code review assistant for the Vein Server Management project._
