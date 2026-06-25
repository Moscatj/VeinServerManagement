# Vein Server Management Suite

A Python + PySide6 toolkit for hosting and supervising a **Vein** dedicated server on Windows.

This project **does not contain the game**.  
It is a management layer that lives alongside your Steam-installed Vein server and handles:

- Starting / stopping the dedicated server
- Crash monitoring and restart logic
- Log tailing and health checks
- Nightly / manual backups
- Discord notifications
- A GUI dashboard for local control

Typical layout on disk:

<VEIN_INSTALL>\                    # Game server install (NOT part of this repo)
<VEIN_MGMT_ROOT>\                  # This repository
📂 Repository Layout
Root (this repo):

VeinServerManagement/
├── AGENTS.md           # AI / Codex rules (this is for tools like Codex)
├── Backups/            # Backup output folders (LastPlayer, Manual, etc.)
├── Config/
│   ├── config.yaml     # Primary config file (YAML)
    config.example.yaml  # Sanitized template copied into release bundles
│   └── Backup/         # Legacy sample/backup configs (JSON/YAML)
├── Controller/
│   ├── config.py           # Config loader (YAML/JSON, env-aware)
│   ├── config_helper.py    # Ergonomic wrapper around config dict
│   ├── crash_monitor.py    # Crash monitor entrypoint
│   ├── monitor_log.py      # Log monitor entrypoint
│   ├── nightly_backup.py   # Scheduled backup helper
│   ├── shutdown_server.py  # Clean shutdown script
│   ├── start_server.py     # Server startup script
?",   ?"o?"??"? vein_tools.py       # CLI dispatcher used by packaged builds
│   ├── Tools/              # Shared helper modules (process, runtime, backups, restart, etc.)
│   ├── vein_manager.py     # PySide6 GUI (main window + StatusPoller)
│   ├── │   │   ├── backups.py
│   │   ├── config_io.py
│   │   ├── discord.py
│   │   ├── log_events.py
│   │   ├── process.py
│   │   ├── state_io.py
│   │   ├── steam_version.py
│   │   ├── update_steam.py
│   │   └── vein_http_api.py
│   └── Legacy/             # Older scripts kept for reference
├── Docs/               # Developer docs (control_layer_overview, Developer_Guide, etc.)
├── Logs/               # Management logs (stdout/stderr from tools)
│   ├── gui/            # VeinManager stdout/stderr, GUI helper output
│   ├── monitors/       # monitor_log/crash_monitor stdout + monitors/http_api/http_api.log
│   ├── controller/     # start/stop scripts and helper subprocess output
│   ├── Archive/        # auto-archived history rotated out of the live folders
│   ├── manifest.json   # metadata for each log emission (subsystem, timestamp, PID, etc.)
│   └── summary.json    # aggregated error summary produced by log_summary.py
├── Runtime/            # PID files, flags, small JSON state (created at runtime)
│   └── player_characters.json  # HTTP API snapshot of online players + characters
├── Scripts/
│   ├── env_setup.bat
BuildInstaller.bat
│   ├── StartServer.bat
│   ├── StartAllMonitors.bat
│   ├── StartServerWithMonitors.bat
│   ├── StartCrashMonitor.bat
│   ├── StartLogMonitor.bat
│   ├── RestartServer.bat
│   ├── Start_VeinManager.bat
│   ├── StopServer.bat
│   └── … (other helpers, health checks, web admin, git hooks, etc.)
└── .git, .gitignore, .gitattributes, etc.
Important:
The Vein game server itself lives elsewhere (for example `<VEIN_INSTALL>\`) and is treated as read-only by this project, aside from reading logs and saves as configured in `Config/config.yaml`.

🧩 Core Components
Controller layer (Controller/)
These scripts form the core “brain” of the management suite:

start_server.py
Launches the Vein server, sets runtime flags, and can start monitors as needed.

crash_monitor.py
Watches for unexpected server termination and handles restart logic / Discord notifications.

monitor_log.py
Tails the Vein log file, tracks freshness, and emits lightweight state JSONs in Runtime/.

nightly_backup.py
Implements scheduled backups and cleanup rules.

shutdown_server.py
Performs clean shutdown:

Marks intentional shutdown

Notifies Discord

Stops monitors

Stops the server process

Optionally triggers backups (based on config)

Clears runtime flags

utils.py (removed)
The former monolithic helper has been fully deleted and will not be recreated.
Its historical responsibilities (process helpers, runtime flags, backup helpers,
Discord senders, Steam update helpers, config summaries, etc.) now live in
dedicated modules inside `Controller/Tools/`, so any new work must continue to
extend those focused helpers instead of reviving `Controller/utils.py`.

config.py / config_helper.py

config.py: Robust loader that searches for Config/config.yaml, config.yml, then legacy config.json (or an override via VEIN_CONFIG).

config_helper.py: Higher-level accessors and convenience functions for reading the config and feature gates.

vein_manager.py
PySide6 GUI:

Main window and tabs

StatusPoller QRunnable to read the small Runtime/ JSONs off the UI thread

Buttons for starting/stopping server and monitors

Filter/search UI for logs/events

Visual health indicators for monitors and server status

HTTP API player browser (Monitors tab) showing admins plus online players/characters pulled from `Runtime/player_characters.json` with double-click detail dialogs

Tools layer (Controller/Tools/)
All shared helpers now live here (process/running state, restart orchestration, backups, Discord helpers, feature gates, paths, etc.). The legacy `utils.py` module has been retired in favor of these focused files.

backups.py — backup plumbing (locations, naming, retention helpers)

config_io.py — config file I/O helpers (JSON/YAML, migration quirks)

discord.py — Discord webhook integration

log_events.py — structured interpretation of Vein log events

process.py — process enumeration, PID inspection

state_io.py — reading/writing runtime state (JSON flags in Runtime/)

steam_version.py / update_steam.py — SteamCMD version checks & updates

vein_http_api.py — any HTTP/API hooks for Vein if present

⚙️ Configuration
The main configuration file is:

Config/config.yaml
Controller/config.py searches in this order:

VEIN_CONFIG environment variable (explicit override)

Config/config.yaml

Config/config.yml

Config/config.yaml (legacy)

Controller-local config.yaml (legacy fallback)

So you can keep using JSON if you like, but YAML (Config/config.yaml) is the current primary format.

Key sections include (see Config/config.yaml and Docs/config_reference.md):

paths.* — server root, runtime dir, saves dir, logs dir, log file, etc.

server.* — arguments, update behavior, startup options.

http_api.* — host/port/scheme for the optional Vein HTTP API (requires matching HTTPPort in Game.ini).

lifecycle.* — quiet windows, restart throttling, shutdown countdowns.

backups.* — paths, schedules, retention strategies.

discord.* — feature flags and webhook configuration.

monitors.* — crash/log monitor intervals and behavior.

🖥️ How to Run It (locally)
These commands assume you are in the VeinServerManagement root folder.

Option A — Use the batch wrappers (recommended on Windows)
Open a terminal in Scripts/.

Initialize the environment:

bat
Copy code
env_setup.bat
Start the server:

bat
Copy code
StartServer.bat
Start monitors (if not started automatically):

bat
Copy code
StartAllMonitors.bat
Start the GUI:

bat
Copy code
Start_VeinManager.bat
Shut down the server cleanly:

bat
Copy code
StopServer.bat
Option B — Direct Python entrypoints
Make sure VEIN_MGMT_ROOT is set or run from the repo root.

bash
Copy code
# Start server
python Controller/start_server.py

# Start crash/log monitors
python Controller/crash_monitor.py
python Controller/monitor_log.py

# Run nightly backup task manually
python Controller/nightly_backup.py

# Open GUI
python Controller/vein_manager.py

# Clean shutdown
python Controller/shutdown_server.py
🧪 Documentation & Developer Info
All deeper technical docs live in Docs/:

Docs/control_layer_overview.md — overall architecture

Docs/Developer_Guide.md — detailed module-by-module breakdown

Docs/config_reference.md — config key reference (JSON-era but still accurate conceptually)

Docs/config_summary.md — quick config overview

Docs/utils_summary.md, Docs/vein_manager_summary.md — focused module summaries

Docs/env_setup_summary.md — environment & batch script overview

Docs/packaging_overview.md -- building the GUI `.exe`, staged bundles, and installer plan

Start with Docs/_index.md if you’re exploring the system.

🧾 Log Utilities
To keep troubleshooting tidy, the suite ships helper scripts that respect `Config/management_logs`:

- `python Controller/logcat.py --search "error"`  
  Grep-style search across any subsystem’s logs with optional `--subsystem monitor_log`, `--since 6h`, `--limit 300`, and `--case-sensitive`.
- Add `--include-archive` if you want to search the logs already rotated into `Logs/Archive/…`.

- `python Controller/log_summary.py`  
  Scans each subsystem’s latest logs for warnings/errors and writes JSON reports to both `Logs/<subsystem>/summary.json` and `Logs/summary.json`.

Both commands rely on the manifest metadata, so CLI output includes paths and line numbers ready for copy/paste.
The GUI mirrors these capabilities: the right-hand log pane now offers **Search Logs**, **Subsystem Log** (with an *Archive Logs* button), and **Errors** tabs so you can grep, browse entire stdout/stderr captures, or review the latest warnings—plus an “Include archive” checkbox if you do want searches to scan `Logs/Archive/`.

🧠 AI / Codex Usage
This repo is designed to work well with tools like OpenAI Codex and GitHub Copilot:

AGENTS.md defines strict rules for AI assistants (what they may / may not touch).

Keep most new shared logic in:

Controller/utils.py, or

small modules in Controller/Tools/.

All config access should go through:

Controller/config.py + Controller/config_helper.py.

When starting a Codex session in VS Code, have it:

Read README.md

Read AGENTS.md

Optionally consult Docs/Developer_Guide.md

Then ask it to propose a small, explicit plan before editing any files.

🤝 Contributing
See CONTRIBUTING.md for guidelines on contributing, branch flow, and coding standards.
