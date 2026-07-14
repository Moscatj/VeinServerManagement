# Coverage Strategy

This project uses coverage as a risk guide, not as a hard 100% target.

The goal is to make backend behavior stable and testable while avoiding brittle
tests that only exist to inflate a percentage. Coverage work should protect
real behavior: config loading, process control, runtime state, backups, log
parsing, Steam helpers, HTTP API helpers, and CLI wrappers.

## Current Baseline

Measured on the v2.9.0 codebase during the 2026-07-14 documentation audit:

- Total tests: 375 passing, 2 skipped
- Overall coverage: 74%
- Backend helper coverage is substantially higher than GUI coverage.

High-value backend coverage:

- `Controller/Tools/backups.py`: 82%
- `Controller/Tools/process.py`: 91%
- `Controller/Tools/runtime.py`: 96%
- `Controller/Tools/server_config_editor.py`: 96%
- `Controller/Tools/server_quickstart.py`: 93%
- `Controller/Tools/steamcmd_runner.py`: 88%
- `Controller/Tools/steam_version.py`: 96%
- `Controller/Tools/update_steam.py`: 98%
- `Controller/Tools/vein_http_api.py`: 99%
- `Controller/Tools/monitors.py`: 100%
- `Controller/Tools/state_io.py`: 100%

Lower coverage is expected in GUI modules because full GUI rendering tests are
more brittle and require more environment setup than backend helper tests.

## Priorities

Prioritize tests for code that can:

- Start, stop, or discover server processes.
- Write runtime state, PID files, lock files, or status flags.
- Copy, zip, prune, or restore backups.
- Read logs and classify events.
- Parse config values and resolve paths.
- Call external tools such as SteamCMD.
- Call HTTP APIs or handle network failures.
- Notify Discord or handle webhook failure behavior.

Use mocks and temporary directories for filesystem, process, network, and Steam
boundaries. Tests must not write to the external Vein game install.

## What To Avoid

Avoid tests that:

- Depend on a running Vein server.
- Depend on a real SteamCMD install.
- Hit real Discord webhooks or HTTP endpoints.
- Assert exact timestamps unless the clock is mocked.
- Assert fragile GUI layout/rendering details.
- Chase uncovered lines that are only import guards, platform-specific branches,
  or defensive fallback code with little practical risk.

## GUI Coverage

GUI coverage can remain lower than backend coverage. Preferred GUI testing
approaches are:

- Test controller/helper seams.
- Mock process, config, and log dependencies.
- Test data transformation and command routing.
- Avoid full-window rendering tests unless a stable UI test harness is added later.

## Future Backend Targets

Good next targets, if more coverage work is desired:

- GUI controller/view seams in `Controller/GUI/config_editor.py`,
  `config_renderer.py`, `logs.py`, and `panels.py` without asserting pixels.
- `Controller/launch_manager.py`: bootstrap failures and packaged/source routing.
- `Controller/Tools/uninstall_cleanup.py`: failure and already-stopped paths.
- `Controller/Tools/discord.py`: disabled channels, webhook failures, payload shaping.
- `Controller/vein_tools.py`: command dispatch and CLI error paths.

## Release Policy

Coverage-only changes are normally `patch` release impact.

Create a release tag only after a meaningful checkpoint, not after every test
commit. Follow `RELEASING.md` for release steps.
