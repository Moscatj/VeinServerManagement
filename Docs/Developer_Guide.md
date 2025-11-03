# Vein Server Management Suite — Developer Guide (v2.1)

> **Purpose:**  
> This document serves as the **comprehensive technical reference** for developers and contributors working on the Vein Server Management Suite.  
> It expands upon the root [README.md](../README.md) by detailing system architecture, environment setup, configuration structure, and internal behavior across all modules.

---

## ⚙️ Overview

The Vein Server Management Suite is a modular control framework for running a **dedicated Vein server** on Windows.  
It provides automated startup, crash recovery, scheduled backups, and Discord notifications — all driven by a single configuration file.

This guide explains the internal design of the v2.1 system, covering environment setup, configuration schema, startup and shutdown sequences, monitoring behavior, and backup automation.

---

## 🧩 Architecture Summary

### Core Components
| File | Purpose |
|------|----------|
| **Controller/start_server.py** | Launches the Vein server. Handles preflight checks, optional Steam updates, runtime flagging, and starts monitors. |
| **Controller/shutdown_server.py** | Performs clean shutdown, sends Discord notifications, and creates backups. |
| **Controller/monitor_log.py** | Tails live logs for player events, autosaves, and crash markers. Posts structured updates to Discord. |
| **Controller/crash_monitor.py** | Detects server crashes, respects quiet/restart windows, and automatically restarts. |
| **Controller/nightly_backup.py** | Creates scheduled Nightly backups and prunes by count/age. |
| **Controller/vein_manager.py** | PySide6 GUI for controlling the server, viewing logs, and editing config. |
| **Controller/utils.py** | Shared logic for process management, backups, Steam updates, and Discord messaging. |
| **Controller/config.py** | Loads, validates, and normalizes `Config/config.json`. Handles defaults and environment overrides. |
| **Controller/config_helper.py** | Provides typed getters and feature gate logic (`is_feature_enabled`, etc.). |
| **Scripts/env_setup.bat** | Initializes all environment variables required by the suite. |
| **Scripts/StartServer.bat** | Calls `env_setup.bat` then launches the Python startup controller. |
| **Scripts/ShutdownServer.bat** | Gracefully stops server and monitors. |

### Supporting Folders
| Folder | Purpose |
|---------|----------|
| **Config/** | Stores `config.json`, the master configuration file. |
| **Runtime/** | Contains transient files (PIDs, state JSONs, flags) written by controllers. |
| **Backups/** | Categorized backup directories: Manual, Startup, Autosave, Crash, and Nightly. |
| **Logs/** | Game log outputs read by the log monitor. |
| **Docs/** | All documentation and technical reference files. |

---

## 🧠 Environment Setup

All launch scripts rely on variables defined in **Scripts/env_setup.bat**:

set VEIN_MGMT_ROOT=G:\Servers\VeinServer\VeinServerManagement
set VEIN_MGMT_CONTROLLER=%VEIN_MGMT_ROOT%\Controller
set VEIN_CONFIG=%VEIN_MGMT_ROOT%\Config\config.json
set PYEXE=py -3

yaml
Copy code

- These variables define paths for all Python controllers.  
- The environment is session-scoped — no registry modifications.  
- Adjust `VEIN_MGMT_ROOT` if the suite is relocated.  

For details, see [Docs/env_setup_summary.md](env_setup_summary.md).

---

## ⚙️ Configuration System

All runtime behavior is controlled by **Config/config.json**.  
See [Docs/config_reference.md](config_reference.md) for detailed key descriptions and defaults.

### Highlights
- Paths and executable lists (`server_dir`, `server_executables[]`)
- Networking (`multi_home_ip`, `game_port`, `query_port`)
- Feature toggles (`enable_crash_monitor`, `enable_discord`, etc.)
- Steam update options (`steamcmd_path`, `app_id`, `validate`)
- Monitoring cadence, heartbeat intervals, and notification preferences
- Backup retention and folder structure

The file is loaded once via `config.py`, cached in memory, and accessed through `config_helper.py`.

---

## 🚀 Startup Sequence (`start_server.py`)

1. **Preflight Checks**
   - Load configuration.
   - Remove stale locks and flags.
   - Validate paths and executables.
   - Post summary to console and Discord.

2. **Maintenance Tasks**
   - Optional SteamCMD update (if enabled).
   - Rotate logs if rotation is active.
   - Create “Startup” backup.

3. **Server Launch**
   - Start the Vein server executable.
   - Write `Runtime/server_running.flag` with PID, executable, and map info.
   - Begin quiet window (`startup_quiet_seconds`) to prevent false crash detection.

4. **Monitor Activation**
   - Start `crash_monitor.py` and `monitor_log.py` in the background.
   - Record state JSONs for GUI display.

---

## 🛑 Shutdown Sequence (`shutdown_server.py`)

1. Mark intentional shutdown (prevents crash monitor restart).  
2. Stop log and crash monitors gracefully.  
3. Send pre-shutdown warning to Discord.  
4. Terminate the server process cleanly (timeout then force).  
5. Create “Shutdown” backup.  
6. Clear runtime flags and locks.  
7. Post completion message to Discord.

---

## 🧩 Crash Recovery (`crash_monitor.py`)

- Runs in a loop (default interval: 60s).  
- Monitors `Runtime/server_running.flag` and checks process health.  
- If missing, confirms quiet window has expired, then:
  - Logs and posts Discord crash alert.
  - Creates a crash backup.
  - Restarts the server after `restart_throttle_seconds`.
- Writes `Runtime/crash_monitor_state.json` for GUI feedback.

---

## 📜 Log Monitoring (`monitor_log.py`)

- Tails the current `Vein.log` (or specified file).  
- Detects:
  - Startup and “joinable” events.
  - Player auth, join, character selection, and disconnects.
  - Autosaves and crash markers.
- Updates `Runtime/log_monitor_state.json` for GUI display.
- Posts messages to Discord via `send_discord_message()`.
- Optional autosave-triggered backups (debounced).

---

## 💾 Backup System

### Categories
| Type | Trigger | Folder |
|------|----------|--------|
| Manual | Manually invoked or GUI-triggered | Backups/Manual |
| Startup | Each successful startup | Backups/Startup |
| Autosave | On autosave detection | Backups/Autosave |
| Crash | On crash detection | Backups/Crash |
| Nightly | Scheduled by Windows Task Scheduler | Backups/Nightly |

### Key Behaviors
- Backups are timestamped ZIPs of the current save file.
- Retention controlled by `max_backups` and `backup_max_age_days`.
- Discord notifications gated by `features.discord_backups`.

---

## 🧭 GUI: Vein Manager (`vein_manager.py`)

Built with **PySide6**, this interface provides:

- **Config Editor**: Tabbed editor with type-aware input fields.  
- **Live Log Viewer**: Streams Vein logs in real time.  
- **Status Indicators**: Color-coded lights for server and monitors.  
- **Start/Stop Controls**: Buttons to manage the server and background scripts.  
- **Runtime State Display**: Reads heartbeat JSONs to show uptime and activity.  

Persistent settings (window layout, overrides) stored via `QSettings`.

---

## 💬 Discord Integration

All Discord messages flow through `utils.send_discord_message()`  
and are controlled by feature flags and channel gates in `config.json`.

| Channel | Events |
|----------|--------|
| **startup** | Preflight + successful start |
| **monitor** | Player activity, autosaves, crash detections |
| **crash_monitor** | Idle, watching, restart, and recovery events |
| **backups** | Backup successes or failures |
| **shutdown** | Warnings and completion notices |

`discord_webhook` supports environment variable resolution using `ENV:VAR_NAME`.

---

## 🕓 Nightly Backup (`nightly_backup.py`)

- Executes a single Nightly backup cycle.  
- Reads Nightly-specific retention (`nightly_backup.*` keys).  
- Calls `utils.backup_save_file()` with reason `"Nightly"`.  
- Prunes old Nightly backups and optionally posts Discord status.  

To schedule:
py -3 Controller\nightly_backup.py

yaml
Copy code
Add to Windows Task Scheduler for automated nightly runs.

---

## 🔧 Utilities (`utils.py`)

Core shared logic for all controllers:
- Process detection and PID management  
- Runtime flag file creation/removal  
- Backup and cleanup functions  
- SteamCMD execution  
- Discord webhook messaging  
- Log rotation  
- Exception-safe filesystem operations  

Every controller imports this module for consistent, reusable functionality.

---

## 🧱 Runtime Files (Runtime/)

| File | Description |
|------|--------------|
| `server_running.flag` | JSON describing the current server process. |
| `startup_in_progress.lock` | Prevents crash monitor from misfiring during boot. |
| `shutdown_in_progress.flag` | Marks controlled shutdowns. |
| `last_restart_at.txt` | Timestamp used for restart throttling. |
| `log_monitor_state.json` | Last heartbeat from log monitor. |
| `crash_monitor_state.json` | Last heartbeat from crash monitor. |

---

## 🧰 Troubleshooting

| Issue | Likely Cause | Fix |
|-------|---------------|-----|
| Server restarts repeatedly | Adjust `startup_quiet_seconds` or `restart_throttle_seconds`. |
| No Discord messages | Check `enable_discord` and webhook environment variable. |
| GUI shows red/yellow gumballs | Verify monitor state JSONs in `Runtime/`. |
| “Already running” warning | Remove stale `.flag`/`.lock` files in `Runtime/`. |
| SteamCMD fails | Increase `steam_update_timeout_seconds` or check credentials. |

---

## 🗂 Folder Summary

VeinServerManagement/
├── Config/config.json
├── Controller/
│ ├── *.py
├── Scripts/
│ ├── env_setup.bat
│ ├── StartServer.bat
│ ├── ShutdownServer.bat
│ ├── StartCrashMonitor.bat
│ └── StartLogMonitor.bat
├── Runtime/
│ └── Live runtime flags/state
├── Backups/
│ ├── Manual/
│ ├── Startup/
│ ├── Autosave/
│ ├── Crash/
│ └── Nightly/
└── Docs/
├── Developer_Guide.md (this file)
├── ...other summaries...

yaml
Copy code

---

## 📘 Documentation Links

- [Root README.md](../README.md) — Quick-start overview  
- [Docs/control_layer_overview.md](control_layer_overview.md) — Architecture overview  
- [Docs/config_reference.md](config_reference.md) — All config keys explained  
- [Docs/start_server_summary.md](start_server_summary.md) — Startup controller details  
- [Docs/vein_manager_summary.md](vein_manager_summary.md) — GUI documentation  
- [Docs/utils_summary.md](utils_summary.md) — Utility function reference  

---

_Last updated: 2025 — Developer Guide for Vein Server Management Suite v2.1_