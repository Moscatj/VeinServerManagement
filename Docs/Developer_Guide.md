# Vein Server Management Suite — Developer Guide (v2.9)

> **Purpose:**
> This document serves as the **comprehensive technical reference** for developers and contributors working on the Vein Server Management Suite.
> It expands upon the root [README.md](../README.md) by detailing system architecture, environment setup, configuration structure, and internal behavior across all modules.

Use [subsystems.yaml](subsystems.yaml) to route a change to its source, focused
tests, documentation, risk, and invariants. Cross-cutting choices that should
not be rediscovered each session are recorded under [decisions/](decisions/).
Use `python Controller/Tools/architecture_check.py --route PATH` for a concise
context report when the affected path is already known.

---

## ⚙️ Overview

The Vein Server Management Suite is a modular control framework for running a **dedicated Vein server** on Windows.
It provides automated startup, crash recovery, scheduled backups, and Discord notifications — all driven by a single configuration file.

This guide explains the v2.9 architecture, including packaged and source
execution, configuration, lifecycle control, monitoring, backups, installer
maintenance, and guarded server configuration.

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
| **Controller/Tools/** | Shared helper modules for process management, backups, Steam updates, Discord messaging, diagnostics, runtime state, and server config validation. |
| **Controller/config.py** | Loads, validates, and normalizes the active local config (`Config/config.yaml` by default). Handles defaults and environment overrides. |
| **Controller/config_helper.py** | Provides typed getters and feature gate logic (`is_feature_enabled`, etc.). |
| **Scripts/env_setup.bat** | Initializes all environment variables required by the suite. |
| **Scripts/StartServer.bat** | Calls `env_setup.bat` then launches the Python startup controller. |
| **Scripts/ShutdownServer.bat** | Gracefully stops server and monitors. |

### Supporting Folders
| Folder | Purpose |
|---------|----------|
| **Config/** | Stores `config.example.yaml` as the tracked template and local-only `config.yaml` for runtime configuration. |
| **Runtime/** | Contains transient files (PIDs, state JSONs, flags) written by controllers. |
| **Backups/** | Categorized backup directories: Manual, Startup, Autosave, Crash, and Nightly. |
| **Logs/** | Management-suite logs, summaries, manifests, and archived controller/monitor output. |
| **Docs/** | All documentation and technical reference files. |

---

## 🧠 Environment Setup

Source batch wrappers call `Scripts/env_setup.bat`, which derives and exports
`VEIN_MGMT_ROOT`, `VEIN_MGMT_SCRIPTS`, and `VEIN_MGMT_CONTROLLER` from the
repository location. Individual wrappers choose their Python launcher and the
controller config loader resolves `VEIN_CONFIG` when explicitly supplied.

Packaged operators do not use the batch environment or need Python. They run
`VeinManager.exe` and `VeinTools.exe` from the installed app root.

- These variables define paths for all Python controllers.
- The environment is session-scoped — no registry modifications.
- The wrapper derives `VEIN_MGMT_ROOT`; do not hardcode it when relocating the
  repository.

For details, see [Docs/env_setup_summary.md](env_setup_summary.md).

---

## ⚙️ Configuration System

All runtime behavior is controlled by the local **Config/config.yaml** file created from **Config/config.example.yaml**.
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
- Updates `Runtime/log_monitor.state.json` (mirrored to the legacy `_state` file) for GUI display.
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

All Discord messages flow through `Controller/Tools/discord.py`
and are controlled by feature flags and channel gates in `config.yaml`.

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
- Calls `Tools.backups.make_backup("Nightly")`.
- Prunes old Nightly backups and optionally posts Discord status.

To schedule:
py -3 Controller\nightly_backup.py

Add to Windows Task Scheduler for automated nightly runs.

---

## 🔧 Shared Tools Modules

The removed monolithic `Controller/utils.py` must not be recreated. Shared
logic lives in focused modules under `Controller/Tools/`, including:

- `process.py` and `runtime.py` for process discovery and lifecycle state;
- `monitors.py` and `restart.py` for monitor/restart orchestration;
- `backups.py` and `backups_api.py` for save-copy backups and retention;
- `discord.py` for webhook routing;
- `paths.py` for canonical save and game-log discovery;
- `server_config_*` and `server_quickstart.py` for validated, guarded setup;
- `steamcmd_runner.py`, `update_steam.py`, and `steam_version.py` for SteamCMD.

See [tools_summary.md](tools_summary.md) for the current module map.

---

## 🧱 Runtime Files (Runtime/)

| File | Description |
|------|--------------|
| `server_running.flag` | JSON describing the current server process. |
| `startup_in_progress.lock` | Prevents crash monitor from misfiring during boot. |
| `shutdown_in_progress.flag` | Marks controlled shutdowns. |
| `last_restart_at.txt` | Timestamp used for restart throttling. |
| `log_monitor.state.json` / `log_monitor_state.json` | Last heartbeat from log monitor (new file mirrors the legacy path). |
| `player_characters.json` | Expanded online player + character/inventory data fetched by `monitor_log.py` for the GUI’s Monitors tab. |
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
├── Config/config.example.yaml
├── Config/config.yaml (local, ignored)
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


---

## 📘 Documentation Links

- [Root README.md](../README.md) — Quick-start overview
- [Docs/control_layer_overview.md](control_layer_overview.md) — Architecture overview
- [Docs/config_reference.md](config_reference.md) — All config keys explained
- [Docs/start_server_summary.md](start_server_summary.md) — Startup controller details
- [Docs/vein_manager_summary.md](vein_manager_summary.md) — GUI documentation
- [Docs/tools_summary.md](tools_summary.md) — Shared Tools module reference

---

_Audited against v2.9.0 on 2026-07-14._
