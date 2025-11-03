# Vein Server Management Suite

A modular, self-healing control system for the **Vein Dedicated Server** on Windows.  
Includes automated backups, crash recovery, Steam updates, and Discord event reporting — all configurable through JSON and managed via an integrated GUI.

---

## 🚀 Features

- ✅ One-click startup with crash + log monitors  
- 🔄 Auto-recovery after crashes or disconnects  
- 🕓 Automated scheduled (nightly) backups  
- 🧩 Full GUI for editing config and viewing logs (`vein_manager.py`)  
- 💬 Discord integration for startup, crash, join, and shutdown events  
- ⚙️ Completely config-driven — no hardcoded paths  

---

## 📁 Project Structure

VeinServerManagement/
├── Config/
│ └── config.json
├── Controller/
│ ├── start_server.py
│ ├── shutdown_server.py
│ ├── crash_monitor.py
│ ├── monitor_log.py
│ ├── nightly_backup.py
│ ├── vein_manager.py
│ ├── config.py
│ ├── config_helper.py
│ └── utils.py
├── Scripts/
│ ├── env_setup.bat
│ ├── StartServer.bat
│ ├── StartCrashMonitor.bat
│ ├── StartLogMonitor.bat
│ └── ShutdownServer.bat
├── Runtime/
│ ├── *.pid / *.json / *.flag
│ └── ...
├── Backups/
│ ├── Manual/
│ ├── Startup/
│ ├── Autosave/
│ ├── Crash/
│ └── Nightly/
└── Docs/
├── utils_summary.md
├── start_server_summary.md
├── monitor_log_summary.md
├── crash_monitor_summary.md
├── shutdown_server_summary.md
├── config_helper_summary.md
├── config_summary.md
├── config_reference.md
├── vein_manager_summary.md
├── nightly_backup_summary.md
├── env_setup_summary.md
└── control_layer_overview.md

yaml
Copy code

---

## ⚙️ Setup

### 1. Prerequisites
- Windows 10/11  
- Python 3.10+  
- SteamCMD (for automatic updates)
- Discord webhook URL (optional but recommended)

### 2. Configure
Edit `Config/config.json` to match your paths and desired behavior.  
See detailed explanations in **[Docs/config_reference.md](Docs/config_reference.md)**.

### 3. Launch Options
| Task | How |
|------|-----|
| Start everything | `Scripts\StartServer.bat` |
| Start monitors only | `Scripts\StartMonitors.bat` |
| Shut down gracefully | `Scripts\ShutdownServer.bat` |
| Use GUI | Run `Controller\vein_manager.py` |
| Run nightly backup | `py Controller\nightly_backup.py` or schedule it |

All batch files automatically call `Scripts/env_setup.bat` to set paths.

---

## 🧩 Core Components

| Module | Summary |
|---------|----------|
| **start_server.py** | Launches the server, applies config, starts monitors. |
| **crash_monitor.py** | Detects unexpected exits, performs controlled restarts. |
| **monitor_log.py** | Parses the live log for player events and crash signatures. |
| **shutdown_server.py** | Performs graceful shutdown + backup. |
| **nightly_backup.py** | Creates and prunes daily “Nightly” backups. |
| **config_helper.py** | Unified getter interface for `config.json`. |
| **vein_manager.py** | Full-featured GUI to manage the suite. |
| **env_setup.bat** | Sets all required environment variables for the suite. |

Full documentation for each file is available in the [Docs](Docs/) folder.

---

## 🧠 Understanding the Control Layer

If you want to understand how the system pieces fit together, read:  
📘 **[Docs/control_layer_overview.md](Docs/control_layer_overview.md)**  
It includes an ASCII flow diagram and cross-module interactions.

---

## 🕓 Automation

To automate nightly backups, schedule:
py -3 Controller\nightly_backup.py

yaml
Copy code
in Windows Task Scheduler.  
See [Docs/nightly_backup_summary.md](Docs/nightly_backup_summary.md) for more details.

---

## 🧰 Troubleshooting

| Issue | Solution |
|-------|-----------|
| Server starts twice | Check for stale `startup_in_progress.lock` in `Runtime/` |
| Crash monitor restarts too fast | Increase `startup_quiet_seconds` or `restart_throttle_seconds` |
| No Discord messages | Verify `enable_discord` and webhook variable |
| GUI gumballs never turn green | Ensure monitor state JSONs are updating under `Runtime/` |

---

## 🧾 Documentation Index

| Topic | File |
|--------|------|
| System Overview | [Docs/control_layer_overview.md](Docs/control_layer_overview.md) |
| Config Reference | [Docs/config_reference.md](Docs/config_reference.md) |
| Configuration Loader | [Docs/config_summary.md](Docs/config_summary.md) |
| Config Helper | [Docs/config_helper_summary.md](Docs/config_helper_summary.md) |
| Server Startup | [Docs/start_server_summary.md](Docs/start_server_summary.md) |
| Shutdown | [Docs/shutdown_server_summary.md](Docs/shutdown_server_summary.md) |
| Crash Monitor | [Docs/crash_monitor_summary.md](Docs/crash_monitor_summary.md) |
| Log Monitor | [Docs/monitor_log_summary.md](Docs/monitor_log_summary.md) |
| Nightly Backup | [Docs/nightly_backup_summary.md](Docs/nightly_backup_summary.md) |
| Environment Setup | [Docs/env_setup_summary.md](Docs/env_setup_summary.md) |
| GUI (Vein Manager) | [Docs/vein_manager_summary.md](Docs/vein_manager_summary.md) |
| Utilities | [Docs/utils_summary.md](Docs/utils_summary.md) |

---

## 🧱 Legacy Technical Notes

For the full deep-dive legacy documentation from v2.1 (“Notify Ready”),  
see **[Docs/Legacy_README_v2.1.md](Docs/Legacy_README_v2.1.md)**.

---

_Last updated by AI documentation generator for the Vein Server Management project._