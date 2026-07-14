# Contributing to Vein Server Management

Thanks for your interest in contributing.

This project currently ships a Windows management suite for the Vein dedicated
server. Native Linux and WSL2 support remain roadmap work. Source development
keeps the game install outside the repository; packaged installs may use an
app-managed `Server\` folder.

## Repository Layout

- `Controller/`: Python entrypoints and GUI code.
- `Controller/Tools/`: shared helper modules.
- `Config/config.example.yaml`: tracked sanitized configuration template.
- `Config/config.yaml`: local runtime configuration file, ignored by Git.
- `Scripts/*.bat`: Windows entrypoints.
- `Docs/`: developer and operator documentation.
- `Runtime/`, `Logs/`, and `Backups/`: generated local state, ignored by Git.

## Getting Started

Clone the repository:

```bash
git clone https://github.com/Moscatj/VeinServerManagement.git
cd VeinServerManagement
```

Use Python 3.11 or newer. A virtual environment is recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
```

Copy `Config/config.example.yaml` to `Config/config.yaml` for your local server install. Do not commit local secrets, local absolute paths, generated state, or user/account files.

## Basic Commands

From the repository root:

```powershell
python Controller\vein_manager.py
python Controller\start_server.py
python Controller\monitor_log.py
python Controller\crash_monitor.py
python Controller\shutdown_server.py
```

Or use the batch files under `Scripts/`:

```powershell
Scripts\TestSuite.bat __RUN__
Scripts\StartServer.bat
Scripts\StartAllMonitors.bat
Scripts\Start_VeinManager.bat
Scripts\StopServer.bat
```

## Coding Guidelines

- Target Python 3.11+.
- Prefer `pathlib` for filesystem work.
- Keep new shared logic in `Controller/Tools/`.
- Do not recreate or import the removed `Controller/utils.py`.
- Use `Controller/config.py` and `Controller/config_helper.py` for config access.
- Avoid hardcoded absolute paths.
- Update docs when behavior or config surface changes.

Use [Docs/documentation_maintenance.md](Docs/documentation_maintenance.md) to
review the appropriate human and AI context for each change. Release work must
synchronize current-version declarations and completed roadmap items rather
than leaving those updates for a later cleanup.

Use [Docs/subsystems.yaml](Docs/subsystems.yaml) to locate the affected source,
focused tests, documentation, risk, and invariants. Review
[Docs/decisions/](Docs/decisions/) before changing a settled cross-cutting
architecture choice. New Python modules under `Controller/` and new
`Tests/test_*.py` files must be assigned to a subsystem. The same applies to
installer definitions, batch/PowerShell scripts, public config templates, and
GitHub workflows selected in `coverage.tracked_groups`; validation rejects
unowned files so the routing map cannot silently fall behind the codebase.

If you touch shutdown, crash detection, backups, or process control, read the related docs first and keep changes small and reviewable.

## Testing

Run the unit suite before opening a pull request:

```powershell
Scripts\ValidateChange.bat
```

New behavior should include unit tests when the behavior is practical to test without starting the Vein server. Bug fixes should include a regression test when practical. If a change is intentionally not unit-tested, explain why in the pull request.

Coverage is used as a risk guide, not a hard 100% target. Read [Docs/coverage_strategy.md](Docs/coverage_strategy.md) before large test-only changes so new tests focus on meaningful backend behavior rather than brittle line coverage.

## Pull Requests

Use a focused branch and include:

- What changed.
- How it was tested.
- Which tests were added or updated, or why tests were not appropriate.
- Coverage impact, if the change is test-focused.
- Any risk to shutdown, backups, crash monitoring, process control, or game-file safety.
- Any config or migration notes.
- Release impact: `none`, `patch`, `minor`, or `major`.

Pull requests should not be merged while CI is failing.

External contributors must use a pull request. The repository owner may use
the validated direct-publish workflow documented in
[Docs/publishing_workflow.md](Docs/publishing_workflow.md); every pushed owner
commit must still pass its GitHub CI run.

For user-facing changes, add a short note to `CHANGELOG.md` under `Unreleased`.

See [RELEASING.md](RELEASING.md) for versioning and release tag rules.

## Issues

Use the GitHub issue templates for bug reports and feature requests. Do not include secrets, webhooks, private logs, save files, or local account data in issues.

## Secret Hygiene

Never commit:

- API keys or webhooks.
- `.env` files.
- Local config overrides.
- Generated coverage data.
- Runtime state, logs, backups, save files, or user-account files.

Use `ENV:VARIABLE_NAME` config values where supported, or document required environment variables.

## AI-Assisted Work

AI-assisted contributions follow the same engineering and review standards as
other changes. Read [AGENTS.md](AGENTS.md) for the authoritative permission,
safety, validation, Git, and release contract, then use
[Docs/docs_for_codex.md](Docs/docs_for_codex.md) as a compact project map.

Review generated changes especially carefully around filesystem boundaries,
installer/SteamCMD behavior, shutdown, backups, process control, monitors,
guarded INI writes, secrets, and GUI thread safety. The contributor remains
responsible for the final diff and test evidence.
