# start_server.py — Summary
**Vein Server Management Suite**

---

## Purpose
`start_server.py` is the dynamic entry point for launching the Vein dedicated server.  
It handles environment setup, configuration loading, process management, monitoring, and Discord startup messaging.

**Core responsibilities:**
- Load and validate the selected config and server executable.
- Refuse duplicate launches and synchronize runtime state to an existing server.
- Optionally update through SteamCMD without making update failure fatal.
- Start log/crash monitors before launching so the full boot is observed.
- Launch the dedicated runtime executable, record its PID/state, and report
  actionable failures through management logs and Discord.

---

## Dependencies
- **config_helper** → loads `config.yaml` and feature toggles.
- **Tools.process** → server discovery, executable launch, and headless flags.
- **Tools.runtime** → startup locks, server state, and restart quiet periods.
- **Tools.monitors** → clean monitor stop/reset before startup.
- **Tools.update_steam** and **Tools.discord** → optional update and status reporting.
- **Tools.mgmt_logs** → packaged/source monitor stdout and stderr capture.

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
  - `startup_quiet_seconds`

---

## Main Functions

### `_spawn_py(script_name)`
- Uses `VeinTools.exe` subcommands in packaged builds and the selected Python
  runtime in source builds.
- Captures monitor output in management-log streams.

### `_start_monitors()`
- Stops stale monitor instances, clears stale PID/stop files, and starts the
  enabled monitors once.

### `_steam_update_if_enabled()`
- Distinguishes success, failure, and unavailable SteamCMD. Startup continues
  with the installed build when an update cannot complete.

### `main()`
**Startup sequence:**
1. Validate config and detect an already-running server.
2. Create the startup lock and publish offline/start state.
3. Optionally run the non-fatal Steam update.
4. Start monitors and give the log monitor a short PID-file settle window.
5. Set the restart quiet period and launch the selected executable.
6. Record the PID and report that the process is waiting to become joinable.
7. Stop newly spawned monitors if launch fails and always clear startup locks.

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
- **Controller/Tools/** → provides process, runtime, monitor, logging, Discord,
  and Steam update functionality.
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
| Change monitor child launching | `_spawn_py()` / `_start_monitors()` |
| Change Steam update narration | `_steam_update_if_enabled()` |
| Change launch orchestration | `main()` |
| Adjust quiet window | `startup_quiet_seconds` config value |

---

_Audited against v2.9.0 on 2026-07-14._
