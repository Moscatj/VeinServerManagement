This workspace follows a consistent coding and design convention
for the Vein Server Management Suite.

Purpose:
The suite manages a dedicated multiplayer server for the game "Vein."
It monitors uptime, detects crashes, restarts automatically, and logs
server events, player activity, and crash information. 
It also communicates these events to a connected Discord channel so that
administrators and players can remotely monitor game and server status.

Discord Integration Guidelines:
- Discord is used to post real-time updates about:
  • Player logins and logouts
  • Server start/stop messages
  • Crash detection and recovery messages
- When adding new features or log events, ensure consistent formatting
  with existing Discord messages (timestamped, clear status prefix).
- Use existing helper functions or APIs for sending Discord messages;
  do not hardcode tokens or webhook URLs in scripts.
- Ensure new Discord notifications provide value to both admins and players
  without spamming repetitive updates.

Python Code Style & Structure:
- Use 4-space indentation, no tabs.
- Follow PEP 8 conventions for naming:
  • snake_case for variables and functions
  • PascalCase for classes
  • ALL_CAPS for constants
- Maintain readability: functions should be short, purposeful, and well-commented.
- Use descriptive variable names; avoid single-letter names unless in loops.
- All string formatting should use f-strings (no % or .format()).
- Keep consistent import ordering: standard library → third-party → local modules.
- Use absolute imports when referencing internal modules (e.g., from Controller import utils).

Logging & Error Handling:
- Use the shared logging functions from utils.py or equivalent.
- All log messages should include timestamps and context.
- Warnings and errors must be clearly labeled for readability.
- When catching exceptions, log the error reason before recovery or re-raise.
- Never suppress exceptions silently.

Configuration Management:
- Always reference configuration paths or options via config.json or a helper loader.
- Avoid hardcoded paths, server executables, or IPs.
- Validate config values gracefully and log warnings for missing or invalid keys.

GUI Conventions (vein_manager.py):
- GUI should follow a clean, minimal layout.
- Buttons and controls should be clearly labeled (Start Server, Stop Server, etc.).
- All actions should update log output and Discord consistently.
- GUI edits to config.json must preserve formatting and structure.

General Practices:
- Document any new function or class with a concise docstring explaining its purpose.
- Test major edits before merging; ensure monitors (log, crash) restart cleanly.
- Maintain cross-module awareness: controllers, GUI, and Discord integrations
  should remain in sync.

When writing or refactoring code, always maintain this tone and structure.
Prefer clarity and maintainability over brevity or over-engineering.
