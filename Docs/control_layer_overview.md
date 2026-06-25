# Control Layer Overview
**Vein Server Management Suite (v2.1)**

This document ties together the main control scripts and their shared dependencies so you — and AI tools — can understand the full system flow at a glance.

---

## 🧩 Core Components

### Primary Controllers
| Script | Role |
|---------|------|
| **start_server.py** | Orchestrates startup: reads config, runs preflight, handles optional Steam update, creates startup backup, launches server process, spawns monitors, and posts Discord startup messages. |
| **monitor_log.py** | Tails the active Vein log; detects joins, disconnects, autosaves, and crashes; writes live state JSONs for GUI and sends Discord messages. |
| **crash_monitor.py** | Monitors runtime state; if the server crashes, triggers a controlled restart while respecting quiet and throttle windows. |
| **shutdown_server.py** | Performs clean, graceful shutdown; stops monitors, posts pre-shutdown and completion messages, and performs a final backup. |
| **nightly_backup.py** | Standalone scheduled task that creates a daily Nightly backup and prunes old archives. |

### Shared Modules
| Module | Purpose |
|---------|----------|
| **Controller/Tools/** | Shared helper modules (process, runtime, restart, backups, Discord, Steam updates). |
| **config.py** | Loads and validates `config.yaml`, applies defaults, and handles environment overrides. |
| **config_helper.py** | Simplified API for retrieving typed config values and feature flags. |

### Support Layers
| Layer | Role |
|--------|------|
| **vein_manager.py** | PySide6 GUI that provides visual control, config editing, live log display, and monitor status indicators. |
| **config.yaml** | Central configuration file defining all paths, features, and behavior. |
| **env_setup.bat** | Initializes environment variables (`VEIN_MGMT_ROOT`, `VEIN_CONFIG`, etc.) for all scripts. |
| **Runtime/** | Folder for live flag/state/heartbeat files used by monitors and the GUI. |
| **Backups/** | Categorized folders for Manual, Startup, Autosave, Crash, and Nightly backups. |

---

## 🧭 ASCII System Diagram

+--------------------------------------------------------------+
| Vein Server Manager |
| (root orchestrator and automation framework) |
+--------------------------------------------------------------+
│
│
▼
┌─────────────────────┐
│ env_setup.bat │ → Defines VEIN_MGMT_ROOT, PYEXE, etc.
└─────────────────────┘
│
▼
┌─────────────────────┐
│ start_server.py │ → Loads config, Steam update, backups, launch server
└─────────────────────┘
│
├─────────────► starts monitor_log.py
│
├─────────────► starts crash_monitor.py
│
└─────────────► writes Runtime/server_running.flag
│
▼
┌──────────────────────────┐
│ Vein Dedicated Server │
│ (Game Process) │
└──────────────────────────┘
│
│ Logs to Vein.log
▼
┌─────────────────────┐
│ monitor_log.py │ → Parses events, updates state JSONs, Discord
└─────────────────────┘
│
▼
┌─────────────────────┐
│ crash_monitor.py │ → Detects server crash or hang, restarts process
└─────────────────────┘
│
▼
┌─────────────────────┐
│ shutdown_server.py │ → Graceful stop, pre-shutdown warning, final backup
└─────────────────────┘
│
▼
┌─────────────────────┐
│ nightly_backup.py │ → Scheduled task for daily backups
└─────────────────────┘
│
▼
┌─────────────────────┐
│ vein_manager.py │ → GUI front-end for all controllers
└─────────────────────┘
│
▼
┌─────────────────────┐
│ Discord Webhooks │ → Startup, crash, join, backup, and shutdown events
└─────────────────────┘

yaml
Copy code

---

## ⚙️ Data Flow

| Step | Producer | Consumer | Data Type |
|------|-----------|-----------|-----------|
| Server PID/flag | `start_server.py` | `crash_monitor.py` | JSON (`server_running.flag`) |
| Log tail state | `monitor_log.py` | `vein_manager.py` | JSON (`log_monitor.state.json`, legacy `_state` file) |
| Player snapshot | `monitor_log.py` | `vein_manager.py` | JSON (`player_characters.json`) |
| HTTP API log | `monitor_log.py` | Operators | Text log (`Logs/monitors/http_api/http_api.log`) |
| Log search CLI | `Controller/logcat.py` | Operators / support | Regex search across all management logs respecting per-subsystem layout |
| Log summary CLI | `Controller/log_summary.py` | Operators / support | Emits JSON summaries (`Logs/summary.json` + per-subsystem `summary.json`) |
| Crash monitor state | `crash_monitor.py` | `vein_manager.py` | JSON (`crash_monitor_state.json`) |
| Backups | `utils.backup_save_file()` | File system | ZIP files |
| Config | `config.py` | All controllers | Dict / cached JSON |
| Discord posts | `utils.send_discord_message()` | Discord webhook | JSON payloads |

---

## 🔄 Process Lifecycle

| Phase | Responsible Script | Summary |
|--------|--------------------|----------|
| Startup | `start_server.py` | Preflight, update, launch, spawn monitors. |
| Monitoring | `monitor_log.py` | Watch logs for player/crash events. |
| Recovery | `crash_monitor.py` | Restart server after failure. |
| Shutdown | `shutdown_server.py` | Clean exit, backup, Discord alert. |
| Nightly Maintenance | `nightly_backup.py` | Scheduled backups and cleanup. |

---

## 🔧 Key Design Notes

- Everything is **config-driven** — no hardcoded paths or constants.
- Controllers communicate **only through runtime files** and **Discord posts** (no sockets).
- All scripts are safe to run independently for testing.
- **GUI** (`vein_manager.py`) never directly controls the game process — it triggers scripts and reads runtime state.
- **Discord integration** lives in `Controller/Tools/discord.py` and is gated by `features.*` in `config.yaml`.
- **Crash prevention** uses restart throttling + startup quiet periods to avoid infinite restart loops.
- All backups and logs are organized by timestamp under `Backups/` and `Runtime/`.

---

_Last updated: 2025 — Vein Server Management contributors_
