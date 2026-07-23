# Vein Server Management Suite Documentation

> **Version baseline:** v2.12.0
> **Maintainers:** Project contributors
> **Purpose:** Central index for all project documentation files.
> Start here when operating, exploring, or extending the management suite.

---

## Project Overview

The Vein Server Management Suite installs, configures, hosts, monitors, and
maintains a dedicated Vein server on Windows. The packaged app includes a
guided installer, GUI, dependency-free operator CLI, SteamCMD integration,
guarded server-config editing, monitoring, backups, and Discord reporting.

For general setup and usage, start with the root-level [README.md](../README.md).
This folder contains all **developer** and **system-level** documentation.

---

## Table of Contents

### System Architecture and Operations
- [control_layer_overview.md](control_layer_overview.md) — High-level architecture and cross-module flow
- [Developer_Guide.md](Developer_Guide.md) — Full developer manual (detailed system design)
- [docs_for_codex.md](docs_for_codex.md) — Compact AI/contributor project map; rules remain in [AGENTS.md](../AGENTS.md)
- [subsystems.yaml](subsystems.yaml) — Authoritative source, test, documentation, risk, and invariant routing map
- [decisions/](decisions/) — Durable architecture decision records
- [env_setup_summary.md](env_setup_summary.md) — Environment initialization (batch setup)
- [config_reference.md](config_reference.md) — Complete `config.yaml` key reference
- [config_summary.md](config_summary.md) — Configuration loader (`config.py`)
- [config_helper_summary.md](config_helper_summary.md) — Helper API for accessing config safely
- [testing.md](testing.md) — Unit test, coverage, and CI expectations
- [coverage_strategy.md](coverage_strategy.md) — Practical coverage priorities and current baseline
- [documentation_maintenance.md](documentation_maintenance.md) — Version, roadmap, readability, and AI-context upkeep
- [publishing_workflow.md](publishing_workflow.md) — Owner direct publishing, shared validation, required remote CI, and contributor pull requests
- [health_check.md](health_check.md) - Read-only project diagnostics and preflight checks
- [management_logs.md](management_logs.md) - Management log layout, retention, archive, and CLI helpers
- [packaging_overview.md](packaging_overview.md) - Windows executable and installer build workflow
- [linux_wsl_support.md](linux_wsl_support.md) - Future native Linux packages, installers, and WSL2 hosting
- [quick_start.md](quick_start.md) - Guarded New Server and Existing Server Quick Start flow
- [gui_modernization.md](gui_modernization.md) - Phased usability, navigation, architecture, and polish plan
- [../ROADMAP.md](../ROADMAP.md) - Current maturity, installer, stability, and future game-config goals

---

### Core Controllers
| Controller | Summary |
|-------------|----------|
| [start_server_summary.md](start_server_summary.md) | Server startup process and preflight checks |
| [shutdown_server_summary.md](shutdown_server_summary.md) | Controlled shutdown sequence |
| [crash_monitor_summary.md](crash_monitor_summary.md) | Crash detection and auto-restart |
| [monitor_log_summary.md](monitor_log_summary.md) | Log monitoring and Discord event parsing |
| [nightly_backup_summary.md](nightly_backup_summary.md) | Nightly backup scheduler and retention logic |

---

### Supporting Modules
| Module | Summary |
|--------|----------|
| [tools_summary.md](tools_summary.md) | Shared Tools modules for processes, backups, Discord, diagnostics, and runtime helpers |
| [vein_manager_summary.md](vein_manager_summary.md) | PySide6 GUI for managing the suite |

---

### Reference and Data
| Topic | File |
|-------|------|
| Config Structure | [config_reference.md](config_reference.md) |
| Environment Setup | [env_setup_summary.md](env_setup_summary.md) |
| Testing and CI | [testing.md](testing.md) |
| Subsystem routing | [subsystems.yaml](subsystems.yaml) |
| Architecture decisions | [decisions/](decisions/) |
| Validated publishing | [publishing_workflow.md](publishing_workflow.md) |
| Coverage Strategy | [coverage_strategy.md](coverage_strategy.md) |
| Health Check | [health_check.md](health_check.md) |
| Server Quick Start | [quick_start.md](quick_start.md) |
| Management Logs | [management_logs.md](management_logs.md) |
| Release Process | [../RELEASING.md](../RELEASING.md) |
| Roadmap | [../ROADMAP.md](../ROADMAP.md) |
| Linux and WSL2 direction | [linux_wsl_support.md](linux_wsl_support.md) |
| Runtime Files | Documented inside [Developer_Guide.md](Developer_Guide.md) |
| Backup System | [nightly_backup_summary.md](nightly_backup_summary.md) + [tools_summary.md](tools_summary.md) |

---

### Advanced Topics
- [Developer_Guide.md](Developer_Guide.md) — Deep technical documentation
- [control_layer_overview.md](control_layer_overview.md) — Architecture and data flow
- [config_helper_summary.md](config_helper_summary.md) — Feature toggles and typed getters
- [vein_manager_summary.md](vein_manager_summary.md) — GUI integration and runtime interaction

---

## Versioning and Maintenance

| Version | Date | Summary |
|----------|------|----------|
| **v2.12.0** | 2026-07-23 | Guarded backup restore, recovery policy, archive management, and Apply-driven settings |
| **v2.11.0** | 2026-07-21 | State-aware setup workflows, isolated lifecycle integration tests, and notification-safe validation |
| **v2.10.0** | 2026-07-14 | Task-oriented GUI, guided Discord setup, startup feedback, and lifecycle hardening |
| **v2.9.1** | 2026-07-14 | Packaged lifecycle CI, documentation/AI workflow hardening, and obsolete-code cleanup |
| **v2.9.0** | 2026-07-13 | Guided installer maintenance, SteamCMD progress/retry, and packaged monitoring/path hardening |
| **v2.8.x** | 2026-07 | GUI foundation, clean-machine lifecycle support, Linux roadmap, and launch hardening |
| **v2.7.0** | 2026-07-10 | Guarded Quick Start for new and existing servers |
| **v2.5.x-v2.6.0** | 2026-07 | Packaged installer, release automation, diagnostics, and guarded INI editing |
| **v2.2.1** | 2026 | Backend test coverage hardening |
| **v2.2.0** | 2026 | Public source hardening baseline, CI, tests, source hygiene, and release process |

The public tag history begins at v2.2.0. See
[CHANGELOG.md](../CHANGELOG.md) for the authoritative release record.

---

## Quick Navigation

Search this folder for terms such as **monitor**, **backup**, **installer**, or
**Discord**.
Each summary file uses consistent section headers so you can quickly find:
- **Purpose**
- **Behavior**
- **Integration Points**
- **Configuration Keys**
- **Example Usage**

---

## Recommended Reading Order

1. [control_layer_overview.md](control_layer_overview.md)
2. [config_reference.md](config_reference.md)
3. [start_server_summary.md](start_server_summary.md)
4. [crash_monitor_summary.md](crash_monitor_summary.md)
5. [monitor_log_summary.md](monitor_log_summary.md)
6. [tools_summary.md](tools_summary.md)
7. [vein_manager_summary.md](vein_manager_summary.md)
8. [nightly_backup_summary.md](nightly_backup_summary.md)

---

## Maintainer Notes

- Primary development environment: Windows 11 with Python 3.12 for packaging.
- Recommended IDE: Visual Studio Code
- AI workflow: follow [AGENTS.md](../AGENTS.md); use
  [docs_for_codex.md](docs_for_codex.md) only as the project map.
- Source wrappers call `env_setup.bat`; packaged users run `VeinManager.exe` or
  `VeinTools.exe` and do not need Python.
- When modifying configuration logic, keep `config.py` and `config_helper.py` synchronized.
- Never put real webhook URLs in tracked docs, tests, or example config.

---

_Audited against v2.9.0 on 2026-07-14._
