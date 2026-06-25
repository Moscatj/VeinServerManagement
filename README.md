# Vein Server Management Suite

A Python and PySide6 toolkit for hosting and supervising a Vein dedicated server on Windows.

This repository does not contain the game server. It is a management layer that lives alongside a Steam-installed Vein dedicated server and handles startup, shutdown, monitoring, backups, and local GUI control.

## Features

- Start, stop, and restart the dedicated server.
- Crash monitoring with restart throttling and intentional-shutdown guards.
- Log monitoring for server health and player events.
- Manual, event-driven, and scheduled backups.
- Discord notifications through environment-backed webhook configuration.
- PySide6 GUI for local administration.
- Unit test and coverage foundation for hardening future changes.

## Repository Layout

```text
AGENTS.md                 AI/Codex safety and workflow rules
CONTRIBUTING.md           Contributor workflow and test expectations
Config/
  config.yaml             Primary config
  config.example.yaml     Sanitized template
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

The actual Vein game install should be outside this repository, for example:

```text
<VEIN_INSTALL>\       Game server install
<VEIN_MGMT_ROOT>\     This repository
```

The management suite may read game logs and saves as configured, but it should not modify game install files.

## Configuration

The primary config file is:

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
```

Do not commit `.env` files, local config overrides, generated runtime state, logs, backups, or user-account files.

## Running Locally

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
```

Common wrappers:

```powershell
Scripts\TestSuite.bat __RUN__
Scripts\StartServer.bat
Scripts\StartAllMonitors.bat
Scripts\Start_VeinManager.bat
Scripts\StopServer.bat
```

## Testing

Code changes should include or update unit tests when practical. At minimum, run:

```powershell
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
```

GitHub Actions runs tests, diagnostics, coverage, and a lightweight secret/local-marker scan on every push and pull request.

Coverage is a guide, not a hard 100% target. The priority is meaningful coverage around config loading, process control, runtime state, backups, log parsing, API helpers, and other behavior that can regress.

## Documentation

Start here:

- [Docs/_index.md](Docs/_index.md)
- [Docs/Developer_Guide.md](Docs/Developer_Guide.md)
- [Docs/control_layer_overview.md](Docs/control_layer_overview.md)
- [Docs/config_reference.md](Docs/config_reference.md)
- [Docs/testing.md](Docs/testing.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Pull requests should describe the change, testing performed, tests added or updated, and any risk to shutdown, backups, crash monitoring, process control, or game-file safety.

## Security And Open-Source Hygiene

Tracked files are scanned for high-confidence secret patterns and local markers in CI. The repository ignores common local-sensitive files including:

- `.env`
- `.continue/.env`
- `.coverage`
- `Config/Backup/`
- `Config/*.local.yaml`
- `Config/*.local.json`
- `Controller/Legacy/WebAdmin/user_accounts.json`
- `Controller/Legacy/WebAdmin/server_state.json`

If a real secret is ever committed, revoke it immediately. Removing a secret from the current tree does not remove it from Git history.
