# vein_manager.py — Summary
**Vein Server Management Suite (GUI Controller)**

---

## Purpose
`vein_manager.py` provides the **graphical user interface (GUI)** for the Vein Server Management Suite.
It allows local administrators to start, stop, and monitor the dedicated Vein game server and its subsystems (log monitor and crash monitor) through an interactive PySide6 interface.

Core goals:
- Provide a visual dashboard for server state (running, offline, or crashed).
- View live game logs directly within the app.
- Edit and validate the server’s YAML configuration files.
- Manage backups, runtime folders, and advanced overrides.
- Launch or stop monitors and server instances with one click.

---

## Architecture Overview
| Layer | Description |
|-------|--------------|
| **UI Components** | Built with PySide6 (`QtWidgets`, `QtCore`, `QtGui`). Tabs, dialogs, and status lights visualize configuration and monitor data. |
| **GUI Helpers** | `Controller/GUI/` hosts emerging reusable widgets that will gradually move layout logic out of `vein_manager.py`. |
| **Controllers** | `Controller/GUI/` modules own process actions, navigation, status rendering, logs, Quick Start, config editing, and dashboard behavior while backend scripts remain the lifecycle authority. |
| **Runtime Helpers** | Manages PID files, flags, runtime directories, and heartbeat files from the `Runtime/` folder. |
| **Persistence** | Saves user overrides and window state via `QSettings`. |
| **Log Tailer** | Streams the live log file within the GUI in real time using a timer-driven file tailer. |

---

## Key Components

### 1. **Main Window (`Main` class)**
Central application controller handling layout, config selection, button wiring, JSON I/O, and background polling. The window is organized around three persistent elements:

1. **Server Control Bar** – persistent `Running`, `Stopped`, or `Setup required` state with one primary action that becomes Set Up, Start, or Stop. Restart remains secondary; log/crash monitor commands live in a compact menu beside a readable monitor summary and selectable result label.
2. **Navigation Column** – task-oriented links for Home, Logs, Backups, Setup,
   Server Settings, and Advanced Config.
3. **Content Stack** – one authoritative workspace that shows the selected page. Logs and Advanced Config are full pages rather than duplicate side-panel tabs, and unfinished destinations are not exposed in normal navigation.

The monitoring dashboard replaces the old “Monitors” tab. It still surfaces log/Crash monitor health, HTTP API world details, the player/character browser (fed by `Runtime/player_characters.json`), and a compact backup card—just with more breathing room for the growing data set. Double-clicking players still opens the detail dialog. Home limits backup information to health, last success, Backup Now, and View Backups. Home and the dedicated Backups page share one non-blocking Backup Now helper and consistent progress/results. The Backups page owns folder access and scans the configured backup root off the GUI thread to show read-only, newest-first save, log, and configuration archive history with category, timestamp, size, and full path. It summarizes total archive count and size, category count, oldest/newest dates, and offers read-only category filtering while limiting table rendering to the newest 200 matches. Its guarded Backup Policy form provides a master backup gate, subordinate Autosave/Crash/Shutdown triggers, independently enabled default count/age cleanup, and a configurable minimum rollback-point floor through Apply-driven review, config backup, atomic write, and post-write validation. Selected save archives can proceed through validation, current-save protection, final confirmation, guarded background activation, verification, and rollback while the server remains stopped.

The configuration editor itself still relies on the generated tabs listed above; selecting a nav entry simply focuses the matching tab so muscle memory continues to work for long-time operators.

---

### 2. **Subprocess Management**
Handles launching and stopping of server and monitors.

Source-mode helpers use the same Python environment that launched the GUI. A
windowless `pythonw.exe` GUI resolves its sibling `python.exe` for captured
helper output; `PYEXE` remains an explicit developer override. Packaged actions
continue to use `VeinTools.exe`.

| Function | Purpose |
|-----------|----------|
| `start_server()` | Launches `start_server.py` in a hidden console. |
| `stop_server()` | Calls `shutdown_server.py`, waits for graceful exit. |
| `restart_server()` | Sequential stop → delayed start. |
| `start_lm()` | Starts the log monitor script; disables in-GUI tail when active. |
| `stop_lm()` | Stops the log monitor (flag + process match fallback). |
| `start_cm()` | Starts the crash monitor. |
| `stop_cm()` | Stops crash monitor with layered retry logic. |

Monitors are identified and stopped by PID file, stop flag, or PowerShell process match.

---

### 3. **Advanced Overrides (`AdvancedDialog`)**
Dialog for customizing script paths and log file overrides without editing the main config.
- Stored in `QSettings` under organization `"VeinServerManagement"`, app `"VeinManager"`.
- Fields include paths to each core controller script and optional log file override.
- “Reset to Defaults” reverts to config.yaml paths.

---

### 4. **About Dialog**
The `Help > About Vein Server Manager` menu opens a copyable version/runtime dialog.
- Shows the installed app version from `version.txt` when packaged.
- Falls back to environment or Git metadata during source/development runs.
- Includes commit, Python, PySide6, Qt, OS, license, repository, app root, and active config path.
- Provides deliberate **Open GitHub Project** and **View release notes** actions.
  Stable packaged versions open their exact tagged release; development builds
  use the latest-release page. Neither link performs a background network check.

---

### 5. **Configuration Editing**
- YAML configs are the primary editable format; legacy JSON remains readable.
- `KVRow` widgets dynamically adapt input fields (checkboxes, numeric inputs, or text fields).
- Users can filter keys or validate syntax before saving.
- `save_atomic()` preserves YAML behavior where supported and replaces the
  selected config atomically.
- Automatic reloading via `QFileSystemWatcher` detects external config edits.

---

### 6. **Status Polling (`StatusPoller`)**
Background worker thread that reads runtime JSON and PID data to determine:
- Whether server, log monitor, and crash monitor are running.
- If log monitor data is fresh or stale.
- Crash monitor mode (“idle”, “watching”, etc.).
- Emits updates every 2 seconds to update status lights and monitor tab labels.

---

### 7. **Live Log Tailer (`FileTail`)**
Watches the selected log file and streams content into the GUI in real time:
- Polls every 1 second, appending new bytes since last position.
- Flushes buffer to UI every 250 ms for smooth scrolling.
- Automatically disables when the external log monitor is running.

---

### 8. **Utilities**
| Function | Description |
|-----------|--------------|
| `_runtime_paths()` | Builds paths to runtime JSONs, flags, and state files. |
| `_rt_paths()` | Similar, but for monitor-specific runtime elements. |
| `_wait_for_monitor_exit()` | Waits for monitor processes to exit gracefully. |
| `_file_exists()`, `_file_text()` | Safe file helpers with exception handling. |
| `_dot()` | Styles colored “gumball” indicators (green/yellow/red). |
| `_age_str()` | Formats elapsed time for heartbeat freshness. |

---

### 9. **UI Experience**
- Phase 1 of the GUI modernization plan introduces shared semantic components
  for page headers, inline notices, status badges, and primary/secondary/danger
  action roles. Styling is narrowly targeted so it follows the active Qt
  palette instead of replacing server workflows or backend behavior.
- Single-workspace layout: a collapsible left navigation column and one content
  stack for Home, Logs, Setup, Server Settings, and Advanced Config. The server
  state and lifecycle controls remain visible above every page.
- The monitor dashboard includes a read-only Server Preflight card that checks
  the selected server root, executable files, Steam API DLL, and key
  `Game.ini` / `Engine.ini` settings off the UI thread. It runs after config
  saves and when the user presses Refresh; it does not run at startup or
  continuously poll static server config files.
- Home begins with an At a Glance summary of server, log monitor, crash monitor,
  and backup health. Its guidance reflects the current runtime state and links
  directly to Setup and Logs when operator attention is needed.
- Server Settings provides focused General, Access, Gameplay, Network, and
  Discord forms. They cover identity, player access, common gameplay rules,
  bind address and ports, and protected VEIN game-chat/admin webhook
  replacement. The Discord page distinguishes these Game.ini integrations from
  the app notifications webhook on Setup. Current non-secret values load into
  one shared dirty-state model; secret values are preserved unless replacements
  are entered. Inline validation covers required names, SteamID64 values, bind
  addresses, unique ports, and Discord webhook URLs. A shared footer keeps
  state, Discard, and Apply actions in one consistent location. Apply generates
  the guarded preview and opens a concise old-to-new confirmation; its optional
  technical details contain the masked INI diff. Tabs containing edits display
  an unsaved marker, and field-specific network and Discord errors appear beside
  the affected controls. Successful writes create backups, run validation, and
  retain a concise validation summary and next-start/restart guidance through
  the automatic settings refresh.
- The original allowlisted `Game.ini` / `Engine.ini` table remains under
  Advanced Settings for individual technical edits. Passwords, webhook URLs,
  token-like values, and sensitive
  unified-diff lines are masked in both views.
- The Setup navigation view classifies the selected root using both filesystem
  evidence and durable installer/GUI setup metadata. New, missing, and
  installer-provisioned servers use four Back/Next pages for Location, Identity
  & Access, Network & Integrations, and Review & Apply. Existing unregistered
  servers use a compact load/connect panel, while completed servers link to
  everyday Server Settings. The wizard generates a copyable plan, blocks
  unrelated populated destinations, and applies game config changes only
  through the guarded backup/diff/validation path.
- Command ribbon condenses all process buttons and exposes a copy-friendly
  status label. A persistent startup strip reports preparation, safeguards,
  process detection, joinable readiness, and failures without blocking the GUI;
  its View Logs action opens the consolidated log workspace. Joinable readiness
  comes from the log monitor's persisted observation of VEIN's ready signature,
  rather than an assumed process state.
- User preferences (geometry, state, last-used paths) persist automatically.
- Shortcut buttons open Logs, Runtime, Backups, or Controller directories.
- Supports dynamic dark/light themes and Windows Fusion style.
- The log pane now includes:
  - **Search Logs** tab (regex + timeframe) powered by the `logcat` worker.
  - “Include archive” checkbox so searches can optionally scan files in `Logs/Archive/`.
  - **Subsystem Log** tab that lists every management subsystem and its recent log files, plus an **Archive Logs** button to rotate live logs into `Logs/Archive/`.
  - **Errors** tab that scans the most recent logs (last hour/day/week presets) and surfaces structured error/warning rows with subsystem/file/level/message metadata.

---

### 10. **Integration Points**
| Module | Used For |
|---------|-----------|
| `Controller/Tools/` | Process, runtime, monitor, logging, backup, path, SteamCMD, and guarded server-config services. |
| `config_helper.py` | Reading normalized paths and feature flags. |
| `start_server.py`, `shutdown_server.py` | Server process control. |
| `monitor_log.py`, `crash_monitor.py` | Real-time monitoring integration. |
| `Runtime/` | All monitor state, heartbeat, and flag files live here. |

---

### 11. **Design Notes**
- Fully Windows-oriented (uses `tasklist`, `os.startfile`, PowerShell).
- Atomic JSON writes prevent corruption on save.
- GUI never blocks during heavy operations (threads + timers).
- Safe fallbacks ensure partial function even if some runtime files are missing.
- Status updates run every 2 seconds and never freeze UI threads.
- Monitor gumballs turn **yellow** when stale but alive, improving visibility.

---

## Example Interaction Flow
1. User opens `Vein Manager`.
2. Manager loads the selected YAML config and runtime states.
3. The user can:
   - Click “Start Server” → runs the source controller or packaged
     `VeinTools.exe start-server` command
   - Toggle monitors (start/stop)
   - Edit configuration directly and save atomically
   - View logs live or rely on external monitor Discord updates
4. The status indicators update automatically based on runtime JSON files.

---

## Quick Reference
| Task | Component |
|------|------------|
| Start/Stop server | Main → `start_server()` / `stop_server()` |
| Manage monitors | `start_lm()` / `start_cm()` / their stop variants |
| Edit config | Tabs + YAML-aware editor + filter |
| Advanced overrides | `AdvancedDialog` |
| Monitor status updates | `StatusPoller` |
| Live log streaming | `FileTail` |
| Save/restore layout | `QSettings` |

---

_Audited against v2.9.0 on 2026-07-14._
