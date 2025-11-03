# start_server.py — Summary
**Vein Server Management Suite**

---

## Purpose
`start_server.py` is the dynamic entry point for launching the Vein dedicated server.  
It handles environment setup, configuration loading, process management, monitoring, and Discord startup messaging.

**Core responsibilities:**
- Initialize the runtime environment and resolve `config.json`.
- Validate the server executable and print a preflight summary.
- Handle pre-existing server instances (restart, skip, or backup).
- Optionally run SteamCMD updates, restore saves, and rotate logs.
- Launch the Vein server and start crash/log monitors as needed.
- Send live Discord messages during each startup stage.

---

## Dependencies
- **config_helper** → loads `config.json` and feature toggles.
- **utils.py** → provides:
  - Server discovery and launch (`find_running_server`, `start_vein_server`)
  - Flag and lock helpers (`create_startup_lock`, `clear_flag`, `end_intentional_shutdown`)
  - Discord notifications
  - Backups, Steam updates, log rotation, quiet window management
- **psutil**, **subprocess**, **pathlib.Path** → process control and I/O.
- Designed for Windows (uses `taskkill`, PowerShell-style command flags).

---

## Key Configuration Values
- `server_dir`, `server_executables[]`
- `map_path` (default `"/Game/Vein/Maps/ChamplainValley?listen"`)
- `max_players` (default `8`)
- `multi_home_ip` (default `"0.0.0.0"`)
- Feature toggles:
  - `features.enable_crash_monitor`
  - `features.enable_log_monitor`
  - `enable_steam_update`
- Behavior toggles:
  - `preboot_shutdown`
  - `backup_on_detect`
  - `shutdown_timeout_sec`
  - `pre_shutdown_warning_seconds`
  - `stale_flag_delay_sec`
  - `show_monitor_window`
  - `startup_quiet_seconds`

---

## Main Functions

### `_print_preflight_summary()`
- Builds a preflight summary showing:
  - Server directory
  - Backup root
  - Executable candidates
  - Map URL, ports, IP, and feature toggles
- Posts a startup summary to Discord.
- Aborts startup if no valid executable is found.

### `_graceful_shutdown(proc, timeout)`
- Attempts to shut down the server gracefully:
  1. Run `shutdown_server.py` if available.
  2. Try `proc.terminate()` and wait.
  3. Fall back to `taskkill /T /F`.
- Ensures clean restarts and prevents orphaned processes.

### `_preflight_guard()`
Handles already-running or stale instances:
- If a live server is found:
  - Sync runtime flag to the actual PID.
  - Optionally:
    - Warn users before shutdown (`pre_shutdown_warning_seconds`)
    - Run backups (`backup_on_detect`)
    - Post restart messages to Discord
    - Gracefully stop the existing server
  - Clears old flags before continuing.
- If no live process but a stale flag exists:
  - Optionally back up files, clear the flag, and continue.

### `_creation_flags(show_window)` / `spawn_once(tag_substring, argv, show_window)`
- Determines process flags for Windows visibility.
- Launches helper monitors only if not already running.

### `maybe_start_monitors(cfg)`
- Starts `crash_monitor.py` and `monitor_log.py` if enabled.
- Uses `spawn_once()` to prevent duplicate processes.

### `main()`
**Startup sequence:**
1. Create startup lock and clear intentional shutdown flags.
2. Print preflight summary and run `_preflight_guard()`.
3. Optionally:
   - Run SteamCMD update.
   - Restore missing saves.
   - Rotate logs.
4. Launch the server via `start_vein_server()` (with correct map, ports, and config).
5. Post Discord “server online” message with PID.
6. Spawn monitors if enabled.
7. Clear startup lock on exit.
8. Handle `KeyboardInterrupt` safely with shutdown cleanup.

---

## Discord Messaging
Sends structured messages to the configured Discord channels for:
- Preflight summary and environment info.
- Restart countdowns.
- Steam update status.
- Successful server launch.
- Startup failures (missing exe, crash).

---

## Runtime Files / Flags
| Purpose | Path | Description |
|----------|------|-------------|
| Server state | `Runtime/server_running.flag` | JSON with PID, executable, map info |
| Startup lock | `Runtime/startup_in_progress.lock` | Prevents false crash triggers |
| Shutdown flag | `Runtime/shutdown_in_progress.flag` | Tracks intentional shutdown |
| Quiet window | `Runtime/last_restart_at.txt` | Used for crash monitor throttle |

---

## Integration Points
- **vein_manager.py** → GUI front-end can call `start_server.py` to start the server.
- **crash_monitor.py** / **monitor_log.py** → spawned here after startup.
- **utils.py** → provides all process, Discord, and backup functionality.
- **config_helper.py** → provides configuration paths and toggles.

---

## Error Handling
- Catches missing executable early and posts a Discord error.
- Always clears startup lock and flags on exit.
- Uses fallback logic for shutdown and restart safety.
- Protects against startup race conditions with locks.

---

## Quick Reference
| Change | Edit Function |
|---------|----------------|
| Adjust startup summary text | `_print_preflight_summary()` |
| Modify restart/skip logic | `_preflight_guard()` |
| Change Steam update sequence | `main()` (Steam section) |
| Add GUI-specific hooks | `maybe_start_monitors()` |
| Adjust quiet window | `startup_quiet_seconds` config value |

---

_Last updated by AI code analysis for the Vein Server Management project._
