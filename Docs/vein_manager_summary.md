# vein_manager.py — Summary  
**Vein Server Management Suite (GUI Controller)**  

---

## Purpose  
`vein_manager.py` provides the **graphical user interface (GUI)** for the Vein Server Management Suite.  
It allows local administrators to start, stop, and monitor the dedicated Vein game server and its subsystems (log monitor and crash monitor) through an interactive PySide6 interface.  

Core goals:
- Provide a visual dashboard for server state (running, offline, or crashed).  
- View live game logs directly within the app.  
- Edit and validate the server’s JSON configuration files.  
- Manage backups, runtime folders, and advanced overrides.  
- Launch or stop monitors and server instances with one click.  

---

## Architecture Overview  
| Layer | Description |
|-------|--------------|
| **UI Components** | Built with PySide6 (`QtWidgets`, `QtCore`, `QtGui`). Tabs, dialogs, and status lights visualize configuration and monitor data. |
| **Controllers** | Interfaces with backend scripts (`start_server.py`, `shutdown_server.py`, `monitor_log.py`, `crash_monitor.py`) via subprocess calls. |
| **Runtime Helpers** | Manages PID files, flags, runtime directories, and heartbeat files from the `Runtime/` folder. |
| **Persistence** | Saves user overrides and window state via `QSettings`. |
| **Log Tailer** | Streams the live log file within the GUI in real time using a timer-driven file tailer. |

---

## Key Components

### 1. **Main Window (`Main` class)**
Central application controller handling:
- UI layout and initialization.
- Configuration file selection.
- Event bindings for all buttons (start/stop/refresh/etc.).
- JSON load/save/validation.
- Background polling for status updates.

#### Tabs:
| Tab | Description |
|------|-------------|
| **Paths** | Editable directory paths and runtime settings. |
| **Server** | Launch parameters (ports, player limits, IPs, etc.). |
| **Steam/Updates** | SteamCMD options and auto-update toggles. |
| **Backups** | Backup paths, retention, and scheduling. |
| **Monitor (simple)** | Flat monitoring parameters (intervals, timeouts). |
| **Monitor (advanced)** | Nested config: tracking, notification, and backup sections. |
| **Features** | Feature flags (log monitor, crash monitor, Discord alerts, etc.). |
| **Top-level** | Unclassified scalars from `config.json`. |
| **Monitors** | Realtime indicators for Log Monitor and Crash Monitor. |

#### Status Panel
Displays:
- Server (green/red light)
- Log Monitor (green/yellow/red)
- Crash Monitor (green/red)
- Current mode and uptime information
- Compact runtime summary (flags present/missing)

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
- Stored in `QSettings` under organization `"RHG"`, app `"VeinManager"`.  
- Fields include paths to each core controller script and optional log file override.  
- “Reset to Defaults” reverts to config.json paths.

---

### 4. **Configuration Editing**
- JSON configs are loaded, parsed, and displayed in a scrollable tabbed editor.
- `KVRow` widgets dynamically adapt input fields (checkboxes, numeric inputs, or text fields).
- Users can filter keys or validate syntax before saving.
- `save_atomic()` writes JSON to a temporary file and atomically replaces the original.
- Automatic reloading via `QFileSystemWatcher` detects external config edits.

---

### 5. **Status Polling (`StatusPoller`)**
Background worker thread that reads runtime JSON and PID data to determine:
- Whether server, log monitor, and crash monitor are running.
- If log monitor data is fresh or stale.
- Crash monitor mode (“idle”, “watching”, etc.).
- Emits updates every 2 seconds to update status lights and monitor tab labels.

---

### 6. **Live Log Tailer (`FileTail`)**
Watches the selected log file and streams content into the GUI in real time:
- Polls every 1 second, appending new bytes since last position.
- Flushes buffer to UI every 250 ms for smooth scrolling.
- Automatically disables when the external log monitor is running.

---

### 7. **Utilities**
| Function | Description |
|-----------|--------------|
| `_runtime_paths()` | Builds paths to runtime JSONs, flags, and state files. |
| `_rt_paths()` | Similar, but for monitor-specific runtime elements. |
| `_wait_for_monitor_exit()` | Waits for monitor processes to exit gracefully. |
| `_file_exists()`, `_file_text()` | Safe file helpers with exception handling. |
| `_dot()` | Styles colored “gumball” indicators (green/yellow/red). |
| `_age_str()` | Formats elapsed time for heartbeat freshness. |

---

### 8. **UI Experience**
- Built using Qt `QMainWindow` with split panels:
  - Left: Config tabs
  - Middle: Raw JSON editor
  - Right: Live log view
- User preferences (geometry, state, last-used paths) persist automatically.
- Shortcut buttons open Logs, Runtime, Backups, or Controller directories.
- Supports dynamic dark/light themes and Windows Fusion style.

---

### 9. **Integration Points**
| Module | Used For |
|---------|-----------|
| `utils.py` | File creation, PID management, and subprocess consistency. |
| `config_helper.py` | Reading normalized paths and feature flags. |
| `start_server.py`, `shutdown_server.py` | Server process control. |
| `monitor_log.py`, `crash_monitor.py` | Real-time monitoring integration. |
| `Runtime/` | All monitor state, heartbeat, and flag files live here. |

---

### 10. **Design Notes**
- Fully Windows-oriented (uses `tasklist`, `os.startfile`, PowerShell).  
- Atomic JSON writes prevent corruption on save.  
- GUI never blocks during heavy operations (threads + timers).  
- Safe fallbacks ensure partial function even if some runtime files are missing.  
- Status updates run every 2 seconds and never freeze UI threads.  
- Monitor gumballs turn **yellow** when stale but alive, improving visibility.

---

## Example Interaction Flow
1. User opens `Vein Manager`.
2. Manager loads the latest `config.json` and runtime states.
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
