# AI Project Guide

This is a compact orientation guide for AI assistants and contributors.
`../AGENTS.md` is the authoritative safety, permission, testing, and release
contract; do not duplicate those rules here.

## Project Snapshot

Vein Server Management Suite is a Windows PySide6 application and packaged CLI
for installing, configuring, running, monitoring, and backing up a Vein
dedicated server. The current stable baseline is v2.9.0. Native Linux and WSL2
support are roadmap targets, not current release capabilities.

Normal packaged users run `VeinManager.exe` and `VeinTools.exe` without Python.
Developers run the Python entrypoints and batch wrappers from the repository.
The Vein server binaries are downloaded separately through SteamCMD and are not
part of this repository.

## Authoritative Sources

| Topic | Source |
|---|---|
| AI permissions and workflow | `AGENTS.md` |
| User entry point | `README.md` |
| Current/future product scope | `ROADMAP.md` |
| Release history | `CHANGELOG.md` |
| Release procedure | `RELEASING.md` |
| Configuration schema | `Config/config.example.yaml`, `Docs/config_reference.md` |
| Architecture | `Docs/control_layer_overview.md`, `Docs/Developer_Guide.md` |
| Tests and coverage | `Docs/testing.md`, `Docs/coverage_strategy.md` |
| Documentation upkeep | `Docs/documentation_maintenance.md` |
| Validated publishing | `Docs/publishing_workflow.md`, `Scripts/ValidateChange.bat`, `Scripts/PublishValidated.bat` |
| Installer behavior | `Docs/packaging_overview.md` |
| GUI refactor direction | `Docs/gui_modernization.md` |

When documentation and code disagree, inspect the implementation and tests,
then update the stale documentation as part of the task.

## Code Map

| Area | Primary locations |
|---|---|
| GUI shell and composition | `Controller/vein_manager.py`, `Controller/GUI/` |
| Start/stop/restart | `Controller/start_server.py`, `Controller/shutdown_server.py`, `Controller/Tools/process.py`, `Controller/Tools/runtime.py`, `Controller/Tools/restart.py` |
| Log/crash monitoring | `Controller/monitor_log.py`, `Controller/crash_monitor.py`, `Controller/Tools/log_events.py`, `Controller/Tools/state_io.py` |
| Backups | `Controller/Tools/backups.py`, `Controller/Tools/backups_api.py`, `Controller/nightly_backup.py` |
| Config loading | `Controller/config.py`, `Controller/config_helper.py`, `Controller/Tools/config_io.py` |
| Quick Start and INI safety | `Controller/Tools/server_quickstart.py`, `Controller/Tools/server_config_editor.py`, `Controller/Tools/server_config_validator.py` |
| SteamCMD | `Controller/Tools/steamcmd_runner.py`, `Controller/Tools/update_steam.py`, `Controller/Tools/steam_version.py` |
| Packaged CLI | `Controller/vein_tools.py` |
| Installer/build | `Installer/VeinServerManager.iss`, `Controller/Tools/packing/`, `Scripts/BuildInstaller.bat` |
| Documentation/version gate | `Controller/Tools/documentation_check.py`, `Docs/documentation_maintenance.md` |
| Management logs | `Controller/Tools/mgmt_logs.py`, `Controller/Tools/log_search.py`, `Controller/logcat.py`, `Controller/log_summary.py` |

`Controller/utils.py` no longer exists. Shared behavior belongs in the relevant
focused module under `Controller/Tools/`.

## Data And Configuration

- `Config/config.example.yaml` is tracked and sanitized.
- `Config/config.yaml` is ignored local state.
- YAML is primary; JSON is legacy compatibility.
- Vein game logs and SaveGames normally derive from `paths.server_root`.
  `game_log.override` and `save_games.override` are advanced exceptions.
- `Logs/` contains management-suite output, not the Vein game log.
- `Runtime/` contains small PID, flag, heartbeat, and state files.
- `Backups/` contains app-created copies and config-edit backups.

Never use real credentials, webhook URLs, private logs, saves, or local absolute
paths in tracked examples or tests.

## Task Routing

Before changing a subsystem, read its implementation, focused tests, and the
matching summary/reference page:

- GUI: `Docs/vein_manager_summary.md`, `Docs/gui_modernization.md`
- lifecycle: `Docs/start_server_summary.md`, `Docs/shutdown_server_summary.md`
- monitors: `Docs/monitor_log_summary.md`, `Docs/crash_monitor_summary.md`
- backups: `Docs/nightly_backup_summary.md`, `Docs/tools_summary.md`
- config: `Docs/config_reference.md`, `Docs/config_summary.md`,
  `Docs/config_helper_summary.md`
- setup/installer: `Docs/quick_start.md`, `Docs/packaging_overview.md`
- Linux/WSL planning: `Docs/linux_wsl_support.md`

Legacy modules under `Controller/Legacy/` are reference-only unless the user
explicitly requests work there.

## Efficient Workflow

1. Read `AGENTS.md`, inspect `git status`, and identify the subsystem from the
   request.
2. Load only the implementation, tests, and references needed for that task.
3. Make a small diff, preserving unrelated work.
4. Add focused tests and update docs when behavior changes.
5. Validate according to the risk tiers in `AGENTS.md`; use
   `Scripts\ValidateChange.bat` for the complete local gate.
6. Report remaining manual or clean-machine testing honestly.

Actively suggest worthwhile workflow improvements, but treat changes to AI
behavior, permissions, approval rules, testing gates, release policy, or
contributor governance as proposals until the user approves them.

Ask a question only when the request is ambiguous, an external/destructive
action needs authority, or a user choice would materially change the result.
