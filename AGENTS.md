# AGENTS.md — Rules for AI Assistants (Codex Agent Mode, ChatGPT, Copilot, etc.)

This document defines **strict rules and safeguards** for AI agents operating on the  
**Vein Server Management Suite**, located at the repository root.

yaml
Copy code

These rules are designed to ensure that agent mode **never edits or damages anything
outside the repository**, never touches the actual Vein game installation, and only
makes safe, reviewable changes.

---

# 1. ABSOLUTE FILESYSTEM BOUNDARIES (CRITICAL)

### ✅ Allowed Write / Edit Area (repo root)
The **only location where the agent may modify, add, or delete files** is the
repository root and its child paths.

markdown
Copy code

This includes:

- All folders under it:
  - `Controller/`
  - `Controller/Tools/`
  - `Config/`
  - `Scripts/`
  - `Docs/`
  - `Backups/` (only writing new backup files)
  - `Runtime/` (writing small JSON/PID files is expected)
  - `Logs/`
- Any new module or file **inside this folder** is allowed.

### ❌ Forbidden Areas (read-only)
The following paths are **strictly read-only**:

<VEIN_INSTALL>
<VEIN_INSTALL>\Saved
<VEIN_INSTALL>\Logs
<VEIN_INSTALL>\Content
<VEIN_INSTALL>\Binaries\

markdown
Copy code

AI MUST NOT:

- Change, delete, or overwrite ANY Vein game file
- Modify game logs (only read them)
- Modify world/save files (only COPY them for backups)
- Patch, update, or delete anything in the Vein folder

**The Vein folder is treated as immutable game data.**

### ✔ Allowed actions in Vein/:
- Reading log files
- Reading save files
- Copying save files (for backups only)

### ❌ Prohibited actions in Vein/:
- Editing files
- Deleting files
- Moving files
- Truncating logs
- Changing permissions
- Renaming directories
- Writing ANYTHING

If an AI ever believes an external write is required, the AI must respond:

> “External file modifications are forbidden without explicit user authorization.”

---

# 2. FILE CREATION / DELETION RULES

### Allowed without permission:
- Creating or editing new Python files **inside**:
  - `Controller/`
  - `Controller/Tools/`
  - `Scripts/`
  - `Docs/`
  - `Config/`

- Writing to:
  - `Logs/`
  - `Runtime/`
  - `Backups/` (only new backup files)

### Requires explicit permission from the user:
- Creating files **in any parent directory**
- Creating files in the parent directory outside the repository
- Creating temporary files outside the repo
- Writing anywhere inside `Vein/`

### Always forbidden:
- Deleting folders outside the repo
- Deleting anything inside `Vein/`
- Deleting user backups unless explicit permission is given
- Modifying system environment variables or registry
- Running high-risk shell commands (`rm -rf`, PowerShell deletions, registry edits)

---

# 3. PROJECT STRUCTURE (Authoritative)

All Python logic exists within the following directories:

### ✔ Main logic  
Controller/

shell
Copy code

### ✔ Shared modules  
Controller/Tools/

shell
Copy code

### ✔ Config  
Config/config.yaml

shell
Copy code

### ✔ Batch wrappers  
Scripts/*.bat

arduino
Copy code

### ✔ Runtime state (read/write)  
Runtime/

shell
Copy code

### ✔ Documentation  
Docs/

yaml
Copy code

---

# 4. DEPRECATION OF utils.py (IMPORTANT)

The file:

Controller/utils.py

markdown
Copy code

is **deprecated**.

### New rules:
- ❌ No new functionality may be added to `utils.py`
- ❌ No major new logic should be placed in `utils.py`
- ✔ Small bug fixes or compatibility patches are allowed temporarily
- ✔ New functionality must be implemented in the appropriate module under:

Controller/Tools/

yaml
Copy code

When unsure where to put new logic, AI must ask:

> “Which Tools module should this functionality belong to?”

---

# 5. CONFIG HANDLING RULES

- Use `Controller/config.py` and `Controller/config_helper.py`
- Do not hardcode absolute paths
- Always honor values in:
Config/config.yaml

yaml
Copy code
- YAML is the primary config; JSON is legacy and must not be expanded
- Agent must not rewrite config to a new format without explicit permission

---

# 6. SAFE SHUTDOWN & BACKUP RULES

These files define the canonical safe shutdown pipeline:

Controller/shutdown_server.py
Controller/utils.py (only for legacy shutdown helpers)
Controller/Tools/backups.py

yaml
Copy code

AI must:

- Preserve intentional shutdown markers
- Preserve Discord notifications
- Respect backup config flags
- Never introduce auto-deletion of saves

Backups must only **copy** save files from the Vein directory.

---

# 7. CRASH & LOG MONITOR RULES

Files:
- `Controller/crash_monitor.py`
- `Controller/monitor_log.py`
- `Controller/Tools/log_events.py`
- `Controller/Tools/state_io.py`

Rules:

- Monitors may only read from Vein logs and saves
- Output must be placed inside `Runtime/`
- Never delete user logs
- Never assume specific log text—use patterns / config

---

# 8. GUI & RUNTIME SAFETY RULES

Applies to:
- `Controller/vein_manager.py`
- `Controller/monitor_log.py`
- `Controller/crash_monitor.py`
- Any long-running helper that executes alongside the game server

Rules:

- Never block the GUI thread (heavy log parsing, disk IO, HTTP calls must use `QRunnable`/background workers)
- GUI must not kill processes directly and must call shared logic from Tools modules
- GUI must not modify game files
- Crash/log monitors must remain lightweight: avoid tight loops, sleep sensibly, and **never** perform work that could impact the Vein server’s CPU/disk usage without user approval
- Any new feature that reads large logs, snapshots saves, or touches runtime state should:
  - Run off the UI thread (if initiated from the GUI)
  - Use bounded work units / sleeps inside monitors
  - Avoid accessing the Vein server filesystem except for allowed read-only operations
- Features that could impact in-game performance (e.g., frequent backups, aggressive scans, high-frequency polling) require explicit user approval before implementation.

---

# 9. CODING STANDARDS FOR NEW WORK

- Use Python 3.11+
- Use type hints where practical
- Use pathlib, not os.path
- Prefer small, focused modules under `Controller/Tools/`
- Avoid circular imports
- Update docs when behavior changes
- Add or update unit tests for new behavior when practical
- Run unit tests before finalizing code changes

---

# 10. AGENT MODE SAFETY RULES

These rules apply to Codex **Agent Mode**.

### Agent Mode MAY:
- Edit files inside VeinServerManagement repo
- Add new modules inside Controller/Tools/
- Update config, docs, or scripts
- Run Git or Python commands **inside the repo only**

### Agent Mode MUST NOT:
- Execute commands outside the repo  
  (e.g., no `cd ..`, no writing to parent directories)
- Touch any file in `<VEIN_INSTALL>\`
- Modify OS-level configuration
- Install software without permission
- Kill processes outside the Vein server

### When unsure:
AI must ask:

> “This action may be destructive or outside the repo. Do you approve?”

---

# 11. SESSION STARTUP CHECKLIST (For AI)

Before performing any task:

1. Read  
   - `README.md`
   - `AGENTS.md`
   - `Docs/docs_for_codex.md`
2. Summarize:
   - Allowed write locations
   - Forbidden areas
   - utils.py deprecation rules
3. Ask:
   > “Which subsystem are we modifying?”
4. Propose a small, reviewable plan
5. Wait for user approval

---

# 12. REQUIRED ACTION APPROVALS

Codex must ask for explicit confirmation before:

- File creation **outside** `VeinServerManagement`
- Deleting any file
- Writing into `Vein/`
- Running shell commands that alter system state
- Changing shutdown or backup behavior

---

# 13. TESTING REQUIREMENTS

Code changes are not considered complete until relevant tests have been run.

Required local checks for normal code changes:

```bat
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
```

AI agents must add or update focused unit tests when changing behavior that can
be exercised without starting the Vein server or writing to the game install.
If tests are not practical, the final response must explain why.

---

# End of AGENTS.md (Agent Mode Safe Edition)
