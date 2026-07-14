# Testing

The project has a `unittest` suite under `Tests/` and a Windows diagnostic wrapper under `Scripts/TestSuite.bat`.

## Required Checks

Run these before finalizing code changes:

```powershell
Scripts\ValidateChange.bat
```

This shared command is also called by GitHub CI and includes the individual
unit, health, diagnostic, coverage, documentation/link, source-hygiene,
architecture/subsystem-registry, and whitespace checks.

The architecture check validates registry paths in both directions. It rejects
missing routed paths and unowned production `Controller/**/*.py`,
`Tests/test_*.py`, installer definitions, scripts, public config templates, or
workflow files selected by `coverage.tracked_groups`. Only narrow patterns
listed under `coverage.exclude` in `Docs/subsystems.yaml` are skipped.
Its optional `--route PATH [PATH ...]` mode also provides a read-only change
context report without altering the validation gate.

`Scripts\TestSuite.bat` now exits non-zero when unit tests fail, so it is safe for automation.
`Controller\health_check.py` exits non-zero on failed diagnostics and allows warnings for optional local dependencies or environment-specific paths.

## Test Policy

- New behavior should include unit tests when the behavior can be exercised without starting the Vein server.
- Bug fixes should include a regression test when practical.
- Config parsing, path handling, runtime state, backups, process control, log parsing, and API helpers should be covered by focused unit tests.
- GUI rendering and long-running monitor loops can be tested through controller/helper seams and mocks rather than brittle full UI tests.
- Tests must not write to the external Vein game install.
- Tests should use `TemporaryDirectory(dir=ROOT)` or mocks for filesystem/process/network boundaries.

## Coverage

Coverage uses `coverage.py` from `requirements-dev.txt`:

```powershell
py -3 -m pip install -r requirements-dev.txt
Scripts\RunCoverage.bat
```

Coverage is a guide, not a hard 100% target. Prefer meaningful tests around risky code over brittle tests that only chase a number.

## Continuous Integration

GitHub Actions runs on every push and pull request:

- Runs the unit suite on supported Python 3.11 and 3.12 runtimes
- Runs the complete repository validation and coverage gate on Python 3.12,
  matching the packaging runtime
- Checks changelog ordering, current-version declarations, release notes, and
  generic version examples with `Controller\Tools\documentation_check.py`
- Installs `requirements-dev.txt`
- Uses `Config/config.example.yaml` as `VEIN_CONFIG`
- Runs unit tests
- Runs the project health check
- Runs `Scripts\TestSuite.bat __RUN__`
- Runs `Scripts\RunCoverage.bat`
- Scans tracked files for high-confidence secrets and local markers
- Builds and uploads a seven-day temporary installer artifact when staged
  bundle, installer, packaging, dependency, or workflow inputs change

The required `Unit Tests And Safety Checks` result aggregates compatibility,
full validation, and the applicable installer build. A failure in any of those
jobs fails the required check rather than leaving a misleading partial success.

The tagged installer workflow reruns the documentation check with `--tag` and
will not package or publish a release whose tag conflicts with the changelog or
documented release baseline.

Pull requests should not be merged while CI is failing.
Owner direct pushes are not considered successfully published until the CI run
for that exact commit passes; see
[publishing_workflow.md](publishing_workflow.md).
