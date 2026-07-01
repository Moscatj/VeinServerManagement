# Testing

The project has a `unittest` suite under `Tests/` and a Windows diagnostic wrapper under `Scripts/TestSuite.bat`.

## Required Checks

Run these before finalizing code changes:

```powershell
python -m unittest discover -s Tests
python Controller\health_check.py
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
```

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

- Installs `requirements-dev.txt`
- Runs unit tests
- Runs the project health check
- Runs `Scripts\TestSuite.bat __RUN__`
- Runs `Scripts\RunCoverage.bat`
- Scans tracked files for high-confidence secrets and local markers

Pull requests should not be merged while CI is failing.
