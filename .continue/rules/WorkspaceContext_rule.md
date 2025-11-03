You are the assistant for the Vein Server Management suite.

This workspace contains all tools and code for managing a dedicated server
for the online multiplayer game "Vein."

The primary goal of the Server Management Suite is to ensure continuous uptime
of the dedicated server by automatically detecting crashes, restarting the
server as needed, and providing live monitoring of server and player activity.

Core directories and their purposes:
- Controller/ — main Python scripts that manage server lifecycle and monitoring:
  • start_server.py: handles startup sequence and runtime process supervision
  • monitor_log.py: monitors game logs for events such as player login/logout, server messages, or errors
  • crash_monitor.py: watches for server process failure and triggers restarts
- Config/ — configuration files (JSON, YAML) containing paths, settings, and runtime toggles
- Scripts/ — Windows batch or PowerShell utilities for launching and maintaining the server environment
- Runtime/ — generated files and state data (PID logs, status flags, etc.); not source-managed
- GUI: vein_manager.py — graphical interface for controlling the server suite

Core functionality:
- Keep the Vein dedicated server online automatically.
- Detect crashes and relaunch the server process quickly.
- Log and monitor in-game events and status (server online, player joins/leaves, etc.).
- Provide a GUI (vein_manager.py) that can:
  • Start, stop, and monitor the server, crash monitor, and log monitor.
  • Edit and save the Config/config.json file.
  • Display live game logs within the GUI to eliminate separate console windows.

Development principles:
- Maintain consistent code style and path handling across all modules.
- Reuse helpers in utils.py and configuration loading logic wherever possible.
- Never propose edits to Backups/ or Logs/ folders.
- Any new feature should integrate cleanly with existing config.json options
  and avoid hardcoding paths or process names.

When editing or reasoning about this project, always consider cross-module
interactions between Controller scripts, the configuration system, and the GUI.
