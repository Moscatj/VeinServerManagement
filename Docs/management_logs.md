# Management Logs

Management logs are logs produced by this management suite, not the live Vein
game logs. The game log monitor reads from the configured Vein install paths,
while management logs stay under the management repository's `Logs/` root.

## Layout

The root is controlled by `management_logs.root`, falling back to
`paths.mgmt_log_dir`. The default is `Logs`.

Subsystem folders are controlled by `management_logs.layout`:

```text
Logs/
  gui/
  controller/start_server/
  controller/shutdown_server/
  monitors/log_monitor/
  monitors/crash_monitor/
  monitors/http_api/
  Archive/
```

`Archive/` is reserved for rotated management logs and is not treated as a
normal subsystem.

## Files

Controller and GUI launch paths use `Controller/Tools/mgmt_logs.py` to allocate
stdout/stderr files. New log allocations update:

- `.latest.json` inside the subsystem folder, used to find the active stream.
- `Logs/manifest.json`, which records recent allocations and metadata.

`Controller/log_summary.py` writes recent warning/error summaries to:

- `Logs/summary.json`
- `<subsystem>/summary.json`

## Retention And Archive

`management_logs.retention` controls how many live `.log` files remain in each
subsystem folder. Older or excess logs are moved to `management_logs.archive.root`
when archive is enabled.

`management_logs.archive` controls archive retention independently from live
subsystem retention.

The archive operation moves management logs only. It must not delete or modify
Vein game logs.

## CLI Helpers

```powershell
python Controller\logcat.py --list
python Controller\logcat.py --search error --include-archive
python Controller\log_summary.py
python Controller\migrate_mgmt_logs.py --dry-run
```

Use `migrate_mgmt_logs.py` to move older top-level `Logs/*.log` files into the
current subsystem layout. Run it with `--dry-run` first.
