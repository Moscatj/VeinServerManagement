# Health Check

`Controller\health_check.py` runs a read-only diagnostic pass for the management
suite. It is intended as a quick preflight before releases, config changes, or
larger refactors.

Run it from the repository root:

```powershell
python Controller\health_check.py
Scripts\HealthCheck.bat
python Controller\health_check.py --json
python Controller\vein_tools.py health-check
```

The command reports `PASS`, `WARN`, and `FAIL` results:

- `FAIL` means a required project dependency, config load, path, or secret-safety
  check failed. The command exits with code `1`.
- `WARN` means the project can still run, but an optional or environment-specific
  item is missing. Warnings do not fail the command.
- `PASS` means the check completed successfully.

The health check may write a tiny temporary probe file only inside existing
management-repo directories such as `Runtime`, `Logs`, or `Backups`, then removes
it immediately. External Vein install paths are checked for existence and
readability only.

Current checks include:

- Config loading through `Controller/config.py`.
- Required Python imports such as `yaml` and `psutil`.
- Optional imports used by runtime or GUI features.
- Management runtime, log, and backup directories.
- Save and game-log paths.
- Configured server executable candidates.
- SteamCMD path availability.
- Discord webhook safety, including detection of raw Discord webhook URLs in
  committed config. Webhooks should use `ENV:...` references.

Use this command as a stability gate alongside the unit test and coverage checks
documented in [testing.md](testing.md).
