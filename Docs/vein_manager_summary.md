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
| **Controllers** | Interfaces with backend scripts (`start_server.py`, `shutdown_server.py`, `monitor_log.py`, `crash_monitor.py`) via subprocess calls. |
| **Runtime Helpers** | Manages PID files, flags, runtime directories, and heartbeat files from the `Runtime/` folder. |
| **Persistence** | Saves user overrides and window state via `QSettings`. |
| **Log Tailer** | Streams the live log file within the GUI in real time using a timer-driven file tailer. |

---

## Key Components

### 1. **Main Window (`Main` class)**
Central application controller handling layout, config selection, button wiring, JSON I/O, and background polling. The window is now organized around three persistent zones:

1. **Command Ribbon** – compact bar with start/stop/restart buttons, LogMon/CrashMon toggles, and a selectable status label so errors can be copied into Discord or issue trackers.
2. **Navigation Column** – shortcut buttons (logs/runtime/backups/controller), a collapsible “Config Source” picker (folder + file combo box), and the `NavigationPanel` with two sections:
   - **Monitoring**: currently hosts the “Server Dashboard” view (live server state, monitors, players, backups).
   - **Configuration**: jump links for `Paths`, `Server`, `Steam/Updates`, `Backups`, `Monitor (simple)`, `Monitor (advanced)`, `Features`, `Top-level`, and the dynamic `Search` tab.
3. **Content Stack + Log Tail** – central stack swaps between the monitoring dashboard and the auto-built config editor while the right-hand log tail stays visible (and collapsible) regardless of view.

The monitoring dashboard replaces the old “Monitors” tab. It still surfaces log/Crash monitor health, HTTP API world details, the player/character browser (fed by `Runtime/player_characters.json`), and backup status/controls—just with more breathing room for the growing data set. Double-clicking players still opens the detail dialog. Backup buttons live in the dashboard card but the logic (`_on_backup_now_clicked`, `_on_open_backups_clicked`) is unchanged.

The configuration editor itself still relies on the generated tabs listed above; selecting a nav entry simply focuses the matching tab so muscle memory continues to work for long-time operators.

---

### 2. **Subprocess Management**
Handles launching and stopping of server and monitors.

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

---

### 5. **Configuration Editing**
- JSON configs are loaded, parsed, and displayed in a scrollable tabbed editor.
- `KVRow` widgets dynamically adapt input fields (checkboxes, numeric inputs, or text fields).
- Users can filter keys or validate syntax before saving.
- `save_atomic()` writes JSON to a temporary file and atomically replaces the original.
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
- Three-way splitter layout: left navigation column (shortcuts + config picker + `NavigationPanel`), center content stack (monitor dashboard + config editor), right live log tail (collapsible but tailer keeps running).
- Command ribbon condenses all process buttons and exposes a copy-friendly status label.
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
| `utils.py` | File creation, PID management, and subprocess consistency. |
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
2. Manager loads the latest `config.yaml` and runtime states.
3. The user can:
   - Click “Start Server” → runs `start_server.py`
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
| Edit config | Tabs + JSON editor + filter |
| Advanced overrides | `AdvancedDialog` |
| Monitor status updates | `StatusPoller` |
| Live log streaming | `FileTail` |
| Save/restore layout | `QSettings` |

---

_Last updated by AI code analysis for the Vein Server Management project._
