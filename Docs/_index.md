# 📘 Vein Server Management Suite — Documentation Index

> **Version:** v2.3.4
> **Maintainers:** Project contributors
> **Purpose:** Central index for all project documentation files.
> Start here if you’re exploring or extending the Vein Server Management system.

---

## 🧩 Project Overview

The Vein Server Management Suite automates hosting, monitoring, and maintaining a **dedicated Vein game server** on Windows.
It handles startup, crash recovery, scheduled backups, and Discord event reporting, all driven by a local `config.yaml` created from the tracked `config.example.yaml` template.

For general setup and usage, start with the root-level [README.md](../README.md).
This folder contains all **developer** and **system-level** documentation.

---

## 📂 Table of Contents

### 🧠 System Architecture
- [control_layer_overview.md](control_layer_overview.md) — High-level architecture and cross-module flow
- [Developer_Guide.md](Developer_Guide.md) — Full developer manual (detailed system design)
- [env_setup_summary.md](env_setup_summary.md) — Environment initialization (batch setup)
- [config_reference.md](config_reference.md) — Complete `config.yaml` key reference
- [config_summary.md](config_summary.md) — Configuration loader (`config.py`)
- [config_helper_summary.md](config_helper_summary.md) — Helper API for accessing config safely
- [testing.md](testing.md) — Unit test, coverage, and CI expectations
- [coverage_strategy.md](coverage_strategy.md) — Practical coverage priorities and current baseline
- [health_check.md](health_check.md) - Read-only project diagnostics and preflight checks
- [management_logs.md](management_logs.md) - Management log layout, retention, archive, and CLI helpers
- [packaging_overview.md](packaging_overview.md) - Windows executable and installer build workflow
- [quick_start.md](quick_start.md) - Server Quick Start planning and future guided setup flow
- [../ROADMAP.md](../ROADMAP.md) - Current maturity, installer, stability, and future game-config goals

---

### ⚙️ Core Controllers
| Controller | Summary |
|-------------|----------|
| [start_server_summary.md](start_server_summary.md) | Server startup process and preflight checks |
| [shutdown_server_summary.md](shutdown_server_summary.md) | Controlled shutdown sequence |
| [crash_monitor_summary.md](crash_monitor_summary.md) | Crash detection and auto-restart |
| [monitor_log_summary.md](monitor_log_summary.md) | Log monitoring and Discord event parsing |
| [nightly_backup_summary.md](nightly_backup_summary.md) | Nightly backup scheduler and retention logic |

---

### 💾 Supporting Modules
| Module | Summary |
|--------|----------|
| [tools_summary.md](tools_summary.md) | Shared Tools modules for processes, backups, Discord, diagnostics, and runtime helpers |
| [vein_manager_summary.md](vein_manager_summary.md) | PySide6 GUI for managing the suite |

---

### 🧱 Reference & Data
| Topic | File |
|-------|------|
| Config Structure | [config_reference.md](config_reference.md) |
| Environment Setup | [env_setup_summary.md](env_setup_summary.md) |
| Testing and CI | [testing.md](testing.md) |
| Coverage Strategy | [coverage_strategy.md](coverage_strategy.md) |
| Health Check | [health_check.md](health_check.md) |
| Server Quick Start | [quick_start.md](quick_start.md) |
| Management Logs | [management_logs.md](management_logs.md) |
| Release Process | [../RELEASING.md](../RELEASING.md) |
| Roadmap | [../ROADMAP.md](../ROADMAP.md) |
| Runtime Files | Documented inside [Developer_Guide.md](Developer_Guide.md) |
| Backup System | [nightly_backup_summary.md](nightly_backup_summary.md) + [tools_summary.md](tools_summary.md) |

---

### 🧰 Advanced Topics
- [Developer_Guide.md](Developer_Guide.md) — Deep technical documentation
- [control_layer_overview.md](control_layer_overview.md) — Architecture and data flow
- [config_helper_summary.md](config_helper_summary.md) — Feature toggles and typed getters
- [vein_manager_summary.md](vein_manager_summary.md) — GUI integration and runtime interaction

---

## 🧾 Versioning & Maintenance

| Version | Date | Summary |
|----------|------|----------|
| **v2.2.1** | 2026 | Backend test coverage hardening |
| **v2.2.0** | 2026 | Public source hardening baseline, CI, tests, source hygiene, and release process |
| **v2.1** | 2025 | Documentation refresh, modular split, and GUI integration |
| **v2.0** | 2024 | Initial stable server + monitor release |
| **v1.x** | 2023 | Pre-release prototypes and manual backups |

---

## 🧭 Quick Navigation (for VS Code users)

If you’re browsing inside VS Code, this folder supports sidebar navigation and search for any keyword like **"monitor"**, **"backup"**, or **"discord"**.
Each summary file uses consistent section headers so you can quickly find:
- **Purpose**
- **Behavior**
- **Integration Points**
- **Configuration Keys**
- **Example Usage**

---

## 🧩 Recommended Reading Order

1. [control_layer_overview.md](control_layer_overview.md)
2. [config_reference.md](config_reference.md)
3. [start_server_summary.md](start_server_summary.md)
4. [crash_monitor_summary.md](crash_monitor_summary.md)
5. [monitor_log_summary.md](monitor_log_summary.md)
6. [tools_summary.md](tools_summary.md)
7. [vein_manager_summary.md](vein_manager_summary.md)
8. [nightly_backup_summary.md](nightly_backup_summary.md)

---

## 🧑‍💻 Maintainers Notes

- Primary Development Environment: Windows 11 + Python 3.11
- Recommended IDE: Visual Studio Code
- Continue AI Integration: Enabled for contextual repo analysis
- Always run scripts via `env_setup.bat` to ensure variables are properly set.
- When modifying configuration logic, keep `config.py` and `config_helper.py` synchronized.
- Discord integration can be tested independently using webhook test URLs.

---

_Last updated: November 2025 — Vein Server Management contributors_
