# Vein Server Management Suite

[![CI](https://github.com/Moscatj/VeinServerManagement/actions/workflows/ci.yml/badge.svg)](https://github.com/Moscatj/VeinServerManagement/actions/workflows/ci.yml)
[![License: Non-Commercial Source Available](https://img.shields.io/badge/License-Non--Commercial%20Source%20Available-blue.svg)](LICENSE)

A Python and PySide6 toolkit for hosting and supervising a Vein dedicated server on Windows.

This repository does not contain the game server. It is a management layer that can either install/manage a Vein dedicated server under the packaged app folder or point at an existing Steam-installed server elsewhere on disk.

## Project Status

This is a personal source-available portfolio project. It is suitable for experimentation and local non-commercial use, with CI, unit tests, and safety-oriented repository rules in place. It is not an official Vein project and does not include commercial support.

## Features

- Start, stop, and restart the dedicated server.
- Crash monitoring with restart throttling and intentional-shutdown guards.
- Log monitoring for server health and player events.
- Manual, event-driven, and scheduled backups.
- Discord notifications through environment-backed webhook configuration.
- PySide6 GUI for local administration.
- Unit test and coverage foundation for hardening future changes.
- Read-only health checks for local paths, SteamCMD, dedicated server files, and key Vein `Game.ini` / `Engine.ini` settings.

## Repository Layout

```text
AGENTS.md                 AI/Codex safety and workflow rules
CONTRIBUTING.md           Contributor workflow and test expectations
Config/
  config.example.yaml     Tracked sanitized template
  config.yaml             Local runtime config, ignored by Git
Controller/
  *.py                    Controller entrypoints
  GUI/                    PySide6 GUI modules
  Tools/                  Shared helper modules
  Legacy/                 Older reference code
Docs/                     Developer and operator documentation
Installer/                Installer scripts/assets
Scripts/                  Windows batch wrappers
Tests/                    Unit tests
Runtime/                  Generated local runtime state, ignored
Logs/                     Generated management logs, ignored
Backups/                  Generated backup output, ignored
```

For source/developer runs, the actual Vein game install should stay outside this repository, for example:

```text
<VEIN_INSTALL>\       Game server install
<VEIN_MGMT_ROOT>\     This repository
```

Packaged installs default to an app-managed layout under the install folder, with `SteamCMD\` and `Server\` beside `VeinManager.exe`. The management suite may read game logs and saves as configured, but it should not modify external game install files outside supported SteamCMD install/update flows.

## Configuration

The tracked public template is:

```text
Config/config.example.yaml
```

Create your local runtime config from that template:

```powershell
Copy-Item Config\config.example.yaml Config\config.yaml
```

`Config/config.yaml` is ignored by Git so local paths, ports, retention settings, and server preferences do not get committed accidentally.

At runtime, the primary local config file is:

```text
Config/config.yaml
```

`Controller/config.py` resolves config in this order:

1. `VEIN_CONFIG` environment variable.
2. `Config/config.yaml`.
3. `Config/config.yml`.
4. Legacy `Config/config.json`.
5. Legacy `Controller/config.json`.

Secrets and local-only values should use environment variables where supported, for example:

```yaml
discord:
  webhooks:
    default: "ENV:DISCORD_WEBHOOK_URL"

steam:
  steamcmd_path: "ENV:STEAMCMD_PATH"
  auto_update_on_start: false
features:
  enable_steam_update: false
```

Do not commit `.env` files, local config files, generated runtime state, logs, backups, or user-account files.

## Running Locally

There are two supported ways to use the project.

For normal users, use the Windows installer from the GitHub Releases page when a packaged release is available. The installer provides:

- `VeinManager.exe` for the GUI.
- `VeinTools.exe` for command-line operations such as health checks, server start/stop, monitor control, and backups.
- A local `Config/config.yaml` copied from the sanitized app-managed template.
- Optional full-package setup that keeps app-managed SteamCMD under `SteamCMD\` and installs a new dedicated server under `Server\` by default.
- Existing-install setup that can point at an existing dedicated server folder, reuse an existing SteamCMD folder, and override the SaveGames/log folders used by monitoring and backups.
- Read-only diagnostics through `VeinTools.exe health-check` and `VeinTools.exe server-config-check`.

The repository itself is the developer/source workflow. Clone it when you want to inspect code, run tests, or build the installer locally.

Install development dependencies:

```powershell
py -3 -m pip install -r requirements-dev.txt
```

Run from the repository root or use the batch wrappers in `Scripts/`.

```powershell
python Controller\vein_manager.py
python Controller\start_server.py
python Controller\monitor_log.py
python Controller\crash_monitor.py
python Controller\shutdown_server.py
python Controller\health_check.py
```

Common wrappers:

```powershell
Scripts\TestSuite.bat __RUN__
Scripts\HealthCheck.bat
Scripts\StartServer.bat
Scripts\StartAllMonitors.bat
Scripts\Start_VeinManager.bat
Scripts\StopServer.bat
```

Packaged CLI examples:

```powershell
VeinTools.exe health-check
VeinTools.exe start-server
VeinTools.exe stop-server
VeinTools.exe stop-all-monitors
```

After a fresh install, run `VeinTools.exe health-check` or use the GUI preflight/status output to confirm the selected server root, `SaveGames`, logs, SteamCMD path, and server executable are all available before starting the server.

## Building The Installer

Packaging is Windows-focused and uses PyInstaller plus Inno Setup 6.

```powershell
py -3.12 -m pip install -r requirements-dev.txt -r requirements-packaging.txt
Scripts\BuildInstaller.bat
```

Python 3.11 or 3.12 is recommended for packaging; Python 3.13 may be unreliable with PyInstaller on this project. Set `PYTHON_BIN` to choose the packaging runtime, for example `set "PYTHON_BIN=py -3.12"`.

By default, `Scripts\BuildInstaller.bat` derives the installer version from the latest Git tag. Set `VEIN_PACKAGE_VERSION` to override it for a local test build. The output installer is written to:

```text
dist\installer\VeinServerManagement-Setup-vX.Y.Z.exe
```

Generated installers and binaries should be published through GitHub Releases, not committed to the repository.
Release tags run the installer workflow and attach a versioned installer, such as `VeinServerManagement-Setup-v2.3.12.exe`, to the GitHub Release.

See [Docs/packaging_overview.md](Docs/packaging_overview.md) for the full packaging workflow.

## Testing

Code changes should include or update unit tests when practical. At minimum, run:

```powershell
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
```

GitHub Actions runs tests, diagnostics, coverage, and a lightweight secret/local-marker scan on every push and pull request.

Coverage is a guide, not a hard 100% target. The priority is meaningful coverage around config loading, process control, runtime state, backups, log parsing, API helpers, and other behavior that can regress. See [Docs/coverage_strategy.md](Docs/coverage_strategy.md) for the testing philosophy and current coverage baseline.

## Documentation

Start here:

- [Docs/_index.md](Docs/_index.md)
- [Docs/Developer_Guide.md](Docs/Developer_Guide.md)
- [Docs/control_layer_overview.md](Docs/control_layer_overview.md)
- [Docs/config_reference.md](Docs/config_reference.md)
- [Docs/testing.md](Docs/testing.md)
- [Docs/coverage_strategy.md](Docs/coverage_strategy.md)
- [Docs/health_check.md](Docs/health_check.md)
- [Docs/management_logs.md](Docs/management_logs.md)
- [CHANGELOG.md](CHANGELOG.md)
- [RELEASING.md](RELEASING.md)
- [ROADMAP.md](ROADMAP.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pull requests should describe the change, testing performed, tests added or updated, and any risk to shutdown, backups, crash monitoring, process control, or game-file safety.

Release tags follow the lightweight semantic versioning policy in [RELEASING.md](RELEASING.md). Normal commits are not automatically tagged; tags mark tested checkpoints on `main`.

## License

This project is free for personal, educational, hobby, community, and other non-commercial use under the [Vein Server Management Non-Commercial Source Available License](LICENSE).

Commercial use is not permitted without a separate written commercial license from the project maintainer. This includes selling the software, bundling it with a paid product or service, offering it as a paid hosted service, or using it primarily to generate revenue.

## Security And Source Hygiene

Tracked files are scanned for high-confidence secret patterns and local markers in CI. The repository ignores common local-sensitive files including:

- `.env`
- `.continue/.env`
- `.coverage`
- `Config/config.yaml`
- `Config/Backup/`
- `Config/*.local.yaml`
- `Config/*.local.json`
- `Controller/Legacy/WebAdmin/user_accounts.json`
- `Controller/Legacy/WebAdmin/server_state.json`

If a real secret is ever committed, revoke it immediately. Removing a secret from the current tree does not remove it from Git history.

For vulnerability reporting guidance, see [SECURITY.md](SECURITY.md).
