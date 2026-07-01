# Contributing to Vein Server Management

Thanks for your interest in contributing.

This project is a Windows-focused management suite for the Vein dedicated server. It is designed to manage a local server install while keeping game files outside the repository.

## Repository Layout

- `Controller/`: Python entrypoints and GUI code.
- `Controller/Tools/`: shared helper modules.
- `Config/config.yaml`: primary configuration file.
- `Config/config.example.yaml`: sanitized configuration template.
- `Scripts/*.bat`: Windows entrypoints.
- `Docs/`: developer and operator documentation.
- `Runtime/`, `Logs/`, and `Backups/`: generated local state, ignored by Git.

## Getting Started

Clone the repository:

```bash
git clone https://github.com/<owner>/VeinServerManagement.git
cd VeinServerManagement
```

Use Python 3.11 or newer. A virtual environment is recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements-dev.txt
```

Copy or edit `Config/config.yaml` for your local server install. Do not commit local secrets, local absolute paths, generated state, or user/account files.

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
Scripts\TestSuite.bat
Scripts\StartServer.bat
Scripts\StartAllMonitors.bat
Scripts\Start_VeinManager.bat
Scripts\StopServer.bat
```

## Coding Guidelines

- Target Python 3.11+.
- Prefer `pathlib` for filesystem work.
- Keep new shared logic in `Controller/Tools/`.
- Do not add new functionality to deprecated `Controller/utils.py`.
- Use `Controller/config.py` and `Controller/config_helper.py` for config access.
- Avoid hardcoded absolute paths.
- Update docs when behavior or config surface changes.

If you touch shutdown, crash detection, backups, or process control, read the related docs first and keep changes small and reviewable.

## Testing

Run the unit suite before opening a pull request:

```powershell
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
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

This project supports AI-assisted development. If using an AI coding assistant:

1. Read `README.md`.
2. Read `AGENTS.md`.
3. Skim `Docs/control_layer_overview.md` and `Docs/Developer_Guide.md`.
4. Confirm that `Config/config.yaml` is the primary config.
5. Confirm that the actual Vein game install is outside the repo and must not be modified.

Review AI-generated changes carefully, especially around filesystem access, shutdown, backups, crash monitoring, and process control.

AI-assisted changes should also classify release impact before finalizing:

- `none`: no release impact.
- `patch`: bug fix, docs, tests, CI, hardening, or non-breaking cleanup.
- `minor`: user-facing feature or meaningful new capability.
- `major`: breaking behavior or large architecture/config change.

For test-only work, AI assistants should follow `Docs/coverage_strategy.md` and prioritize backend risk reduction over raw percentage increases.
