# Vein Server Control Suite — v2.1 “Notify Ready”

A fully configurable, self-healing control suite for the **Vein Dedicated Server** on Windows 11 — featuring automatic Steam updates, crash recovery, backups, and Discord integration for every stage of the server lifecycle.

---

## 📁 Directory Layout

G:\Servers\VeinServer
├── StartSuite_tabs.bat # Unified startup (server + monitors in one tabbed window)
├── StartServer.bat # Start only the server
├── StartMonitors.bat # Classic dual-monitor start
├── StartMonitors_tab.bat # Monitors in a single tabbed console
├── ShutdownServer.bat # Full graceful shutdown (Admin required)
└── /Tools/
├── config.json
├── config_helper.py
├── utils.py
├── start_server.py
├── shutdown_server.py
├── crash_monitor.py
└── monitor_log.py

yaml
Copy code

---

## ⚙️ Config Reference (`config.json`)

All adjustable behavior lives in `Tools/config.json`.  
No hard-coded paths — everything resolves through `config_helper`.

### Core Settings

| Key | Description |
|-----|--------------|
| `server_dir` | Folder containing the Vein server executables |
| `server_executables` | List of accepted EXE filenames |
| `map_path` | Unreal map path (omit `?listen`) |
| `multi_home_ip` | IP to bind (use `0.0.0.0` for all interfaces) |
| `game_port` / `query_port` | Game and query ports |
| `extra_launch_args` | Extra Unreal arguments (e.g. `-SteamSockets`) |
| `steamcmd_path` | Full path to SteamCMD |
| `app_id` | Vein App ID 2131400 |
| `auto_update_on_start` | Run Steam update before each boot |
| `backup_root` | Root directory for all backups |
| `save_dir` / `save_filenames` | Save file locations |
| `discord_webhook` | Webhook URL or `ENV:DISCORD_WEBHOOK_URL` |
| `shutdown_timeout_sec` | Time to wait for graceful exit |
| `pre_shutdown_warning_seconds` | Optional Discord countdown before shutdown |

---

### 🧩 Monitor Configuration (`monitor` block)

| Key | Purpose |
|-----|--------|
| `enable` | Master toggle for `monitor_log.py` |
| `heartbeat_interval_seconds` | Seconds between heartbeat updates (default 3600 = hourly) |
| `state_file` | Optional override path for `server_state.json` |

#### 🧠 Tracking Toggles (`monitor.track`)
```json
"track": {
  "startup": true,
  "auth": true,
  "join": true,
  "character": true,
  "disconnect": true,
  "autosave": true,
  "crash": true,
  "heartbeat": true
}

Disabling a track item stops it from being processed entirely.

🔔 Notification Toggles (monitor.notify)
"notify": {
  "startup": true,
  "joinable": true,
  "auth": true,
  "join": true,
  "character": true,
  "disconnect": true,
  "autosave": false,
  "crash": true,
  "heartbeat": false,
  "monitor_status": true
}
Set any value to false to silence that event in Discord while keeping console and state updates active.

💾 Backup Triggers (monitor.backups)
"backups": {
  "on_player_logout": true,
  "on_autosave": true
}
Automatically creates labeled ZIP backups during player logouts or autosaves.

🔧 Feature Flags (features block)
Key	Description
enable_discord	Master Discord on/off
enable_backups	Enable all backup creation and rotation
enable_steam_update	Run SteamCMD pre-launch
enable_crash_monitor	Enable crash monitor process
enable_log_rotation	Periodic Vein.log rotation
discord_*	Per-channel toggles (monitor, startup, shutdown, backups, crash_monitor)

🖥 Server Lifecycle Commands
Command	Function
StartSuite_tabs.bat	Launches server + both monitors in one tabbed terminal (recommended)
StartServer.bat	Starts server only
StartMonitors_tab.bat	Starts only log & crash monitors
ShutdownServer.bat	Performs full controlled shutdown and backup

🛑 Shutdown Sequence
ShutdownServer.bat performs:

Gracefully stops monitors.

Sends optional Discord countdown (pre_shutdown_warning_seconds).

Terminates all VeinServer*.exe and UE helper processes.

Performs Shutdown backup.

Clears flags and lock files.

Posts final “Server stopped” message to Discord (if enabled).

Requires Administrator rights.

💥 Crash & Exception Recovery
crash_monitor.py watches for unexpected exits.

On detection:

Posts crash alert (respecting notify.crash).

Sends last N log lines (gated by same flag).

Performs backup.

Waits out quiet window before restarting.

📊 Log Monitoring (monitor_log.py)
Continuously follows Vein.log and reacts to:

Player authentication, joins, and disconnects

Character selection

Auto-saves (with cooldown backups)

Fatal/crash signatures

Heartbeats summarizing uptime and player list

Heartbeats
Default: every hour (heartbeat_interval_seconds: 3600)

Controlled by track.heartbeat and notify.heartbeat.

Heartbeats always print to console and update the WebAdmin state file.

Discord posting only occurs if both flags are true.

🧱 Safety & Reliability
Startup locks prevent duplicate boots.

Quiet windows stop restart loops after manual restarts.

Crash-aware backups keep save data safe.

Discord secrets pulled from environment variables.

Graceful shutdown ensures process cleanup before restart.

🔔 Discord Webhook Handling
Set system variable DISCORD_WEBHOOK_URL.

In config.json, specify "discord_webhook": "ENV:DISCORD_WEBHOOK_URL".

The suite auto-loads it at runtime.

🧩 Troubleshooting
🔹 Heartbeats spamming Discord
Set "monitor.notify.heartbeat": false or raise "heartbeat_interval_seconds" to 3600 or higher.

🔹 No Discord messages
Check:

"features.enable_discord": true

Environment variable DISCORD_WEBHOOK_URL is set correctly

The corresponding "monitor.notify" flag isn’t disabled

🔹 Log monitor not stopping
Run ShutdownServer.bat as Administrator to terminate background processes.

🔹 Steam update timeout
Disable "auto_update_on_start" temporarily or increase "steam_update_timeout_seconds".

✅ Summary
Fully config-driven, zero hard-coded paths.

Modular monitors with per-event tracking and Discord notification toggles.

Hourly heartbeat default, safe backups, and robust crash recovery.

Designed for Windows 11 tabbed terminals with full admin cleanup support.

Vein Server Control Suite v2.1 — Reliable · Recoverable · Refined