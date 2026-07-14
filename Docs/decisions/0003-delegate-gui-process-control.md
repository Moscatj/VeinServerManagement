# 0003 — Delegate GUI Process Control

**Status:** Accepted

## Context

Duplicating start, stop, restart, monitor, and shutdown behavior in GUI handlers
creates inconsistent safety behavior and makes long-running work likely to block
the UI thread.

## Decision

The GUI delegates server and monitor mutations to shared controller and
`Controller/Tools` logic. Blocking work uses workers or subprocesses. GUI code
may perform a signal-zero liveness probe but may not directly terminate managed
processes.

## Consequences

CLI, packaged, and GUI workflows share lifecycle safeguards and focused tests.
New lifecycle behavior belongs in shared logic before it is exposed through a
button or panel.

See [control_layer_overview.md](../control_layer_overview.md) and
[vein_manager_summary.md](../vein_manager_summary.md).
