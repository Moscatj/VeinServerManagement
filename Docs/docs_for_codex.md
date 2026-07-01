# docs_for_codex — Quick Guide for AI Assistants

This document is for AI tools (OpenAI Codex, ChatGPT, Copilot, etc.) working on the **Vein Server Management** project.

If you are not an AI, you probably want `README.md` or `Docs/Developer_Guide.md` instead.

---

## 1. What This Project Is

- A **management suite** for the **Vein** dedicated server.
- Runs on the same Windows PC where the user plays the game.
- Handles:
  - Starting/stopping the Vein server
  - Crash monitoring & auto-restart
  - Log monitoring
  - Nightly/manual backups
  - Discord webhook notifications
  - GUI dashboard (PySide6)

> The actual game server binary is **not** part of this repo and must not be modified.

---

## 2. Directory Map (For AI)

**Repo root:** `VeinServerManagement/`

Key folders and files:

- `Config/`
  - `config.yaml` — primary configuration file (YAML)
  - `Backup/` — old sample configs / backups (JSON/YAML)

- `Controller/`
  - `start_server.py` – starts the Vein dedicated server
  - `shutdown_server.py` — orchestrates **safe shutdown** (CRITICAL)
  - `crash_monitor.py` — process crash monitor
  - `monitor_log.py` — log tail / freshness monitor
  - `nightly_backup.py` — scheduled backup logic
  - `Controller/Tools/` modules — shared helpers (processes, runtime flags, backups, Discord)
  - `config.py` — robust config loader (YAML/JSON, env override)
  - `config_helper.py` — ergonomic wrapper around loaded config
  - `vein_manager.py` – PySide6 GUI (includes `StatusPoller` QRunnable)
  - `logcat.py` – CLI log search across management subsystems (supports `--include-archive` to scan `Logs/Archive/`)
  - `log_summary.py` – emits JSON summaries of recent log warnings/errors
  - `Legacy/` — older scripts kept for reference (read-only unless user asks)

- `Controller/Tools/`
  - `backups.py` — backup plumbing (locations, retention helpers)
  - `config_io.py` — config file I/O helpers (JSON/YAML)
  - `discord.py` — Discord webhook send helpers
  - `mgmt_logs.py` - management-log layout, manifest, retention, and archive helpers
  - `log_events.py` — parse/interpret Vein log events
  - `process.py` — process discovery, PID checks
  - `state_io.py` — read/write small JSON state files in `Runtime/`
  - `steam_version.py` — check current Steam build version
  - `update_steam.py` — SteamCMD update helper
  - `vein_http_api.py` — hooks for Vein HTTP API (if used)

- `Scripts/`
  - `env_setup.bat` — sets environment vars (paths, PYTHONPATH, etc.)
  - `StartServer.bat`, `StartAllMonitors.bat`, `Start_VeinManager.bat`, `StopServer.bat`, etc.
  - These are Windows-oriented entrypoints around the controller scripts.

- `Runtime/`
  - Created at runtime.
  - Contains PID files, lock files, and small JSONs consumed by the GUI & monitors.

- `Backups/`
  - Output from backup routines (manual, nightly, autosave, etc.)

- `Logs/`
  - Per-subsystem management logs (GUI, monitors, controller helpers) plus `Archive/` for rotated history.
  - This is separate from the Vein game install logs under the configured `paths.logs_dir`.
  - `manifest.json` (metadata for every log emission) and `summary.json` (latest aggregated warnings/errors).

- `Docs/`
  - `_index.md` — docs index
  - `control_layer_overview.md` — high-level architecture
  - `Developer_Guide.md` — deeper technical breakdown
  - `*_summary.md` — short summaries per major script

---

## 3. Things AI Must ALWAYS Respect

1. **Config is king**
   - Use `Controller/config.py` + `Controller/config_helper.py` for config.
   - Do *not* hardcode absolute paths.
   - Primary config: `Config/config.yaml`, with JSON as legacy fallback.

2. **Safe shutdown is sacred**
   - `Controller/shutdown_server.py` + `Controller/Tools/` (runtime/backups/process/restart) form the canonical shutdown pipeline.
   - Do **not**:
     - Kill the Vein process directly from the GUI.
     - Change shutdown order without a clear reason & explanation.
     - Remove or bypass Discord notifications.
     - Delete save files or backups.

3. **External Vein directory is off-limits**
   - The actual game install (for example `<VEIN_INSTALL>\`) is outside this repo.
   - Do **not** write to game binaries or Steam files.
   - Only touch game dirs/saves/logs in ways already supported by config + backup logic.

4. **GUI must stay responsive**
   - Heavy work (disk, process polling, log tailing) stays in:
     - `StatusPoller` (QRunnable)
     - separate scripts (`crash_monitor.py`, `monitor_log.py`)
   - No blocking operations on the UI thread in `vein_manager.py`.

---

## 4. Typical Tasks Codex Will Be Asked To Do

These are examples of the kinds of work you’ll likely be asked to perform and where to do it.

### 4.1 Refactor / improve the GUI filter & search

- Primary file: `Controller/vein_manager.py`
- Secondary context: `Docs/vein_manager_summary.md`
- Goals usually include:
  - Fixing filter bugs
  - Improving tab counts & search behavior
  - Keeping work off the UI thread

**Example prompt:**

> You are working in Controller/vein_manager.py.  
> Read this file and Docs/vein_manager_summary.md.  
> The search/filter behavior is glitchy (tab counts wrong, occasional crashes).  
> Refactor the filter/search logic so:
> - No AttributeErrors occur when a row is missing a label.
> - Tab counts always reflect the filtered set.
> - The UI remains responsive (no blocking work on the main thread).  
> Show a unified diff for your changes.

---

### 4.2 Add or adjust backup behavior

- Files:
  - `Controller/nightly_backup.py`
  - `Controller/Tools/backups.py`
  - `Config/config.yaml`
- Goals:
  - Introduce new backup modes
  - Adjust retention policy
  - Add new config flag(s)

**Example prompt:**

> I want a new backup mode: "pre-shutdown backup" triggered only on intentional shutdowns.  
> Please:
> - Inspect Controller/shutdown_server.py, Controller/Tools/ (process/runtime/restart/backups), and Config/config.yaml.
> - Propose a plan to add a config flag `backups.pre_shutdown.enabled` and implement it so that:
>   - On intentional shutdown, if enabled, a backup is taken before the server is killed.
>   - If backups are disabled globally, behavior does not change.
> - After I approve the plan, implement the changes and show a unified diff for each file.

---

### 4.3 Improve crash monitoring / log monitoring

- Files:
  - `Controller/crash_monitor.py`
  - `Controller/monitor_log.py`
  - `Controller/Tools/log_events.py`
  - `Controller/Tools/state_io.py`
  - `Docs/crash_monitor_summary.md`, `Docs/monitor_log_summary.md`

**Example prompt:**

> I want to extend the log monitor to detect when the server is "stuck" (no new log lines for X minutes) and flag it in the Runtime state JSON.  
> Please:
> - Read Controller/monitor_log.py, Controller/Tools/log_events.py, Controller/Tools/state_io.py, and Docs/monitor_log_summary.md.
> - Propose a minimal change that:
>   - Tracks when a log was last updated.
>   - Writes a boolean "stale_log" field into the runtime JSON.
>   - Does not block or spin in tight loops.
> - After I approve, implement the changes and show unified diffs.

---

### 4.4 Improve config ergonomics

- Files:
  - `Controller/config.py`
  - `Controller/config_helper.py`
  - `Config/config.yaml`
  - `Docs/config_summary.md`, `Docs/config_helper_summary.md`

**Example prompt:**

> I’d like to add a helper in config_helper.py to get an absolute path to the primary log file, respecting both logs_dir and absolute_log_file from config.  
> Please:
> - Read Controller/config.py, Controller/config_helper.py, and Docs/config_helper_summary.md.
> - Implement a function `get_log_file_path()` that:
>   - Returns pathlib.Path
>   - Prefers `paths.absolute_log_file` if set.
>   - Otherwise constructs a path from `paths.logs_dir` and `paths.log_file`.
> - Update any obvious call sites that manually perform this logic.

---

## 5. What NOT To Do

AI tools should **NOT**:

- Touch the external Vein game install directory (binaries, Steam files).
- Introduce new destructive operations on save files or backups.
- Change the shutdown order or default behavior silently.
- Remove or bypass Discord notifications around crashes/shutdowns/startups.
- Add long-running or blocking operations directly inside PySide6 event handlers.
- Create new entrypoints without documenting them in `Docs/` and/or `README.md`.

---

## 6. Startup Checklist for Codex

When a new AI session is started on this repo, it should:

1. Read:
   - `README.md`
   - `AGENTS.md`
   - `Docs/control_layer_overview.md`
   - `Docs/Developer_Guide.md` (as needed)
2. Ask the human:
   - “Which subsystem are we changing? (GUI, config, crash monitor, log monitor, backups, Discord, Steam updates, etc.)”
3. Propose a short, clear plan.
4. Apply changes as **small diffs** to:
   - `Controller/*.py`
   - `Controller/Tools/*.py`
   - `Config/config.yaml`
   - `Docs/*.md` (if behavior changes)

---

End of docs_for_codex.
