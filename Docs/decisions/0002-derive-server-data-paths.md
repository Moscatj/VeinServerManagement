# 0002 — Derive Game Log and Save Paths

**Status:** Accepted

## Context

Vein owns its game log and save layout. Asking novice operators to select every
derived directory created confusing installer choices and stale paths after a
server was moved.

## Decision

Treat the selected server root as authoritative and derive the normal Vein game
log and SaveGames paths from it. Keep explicit overrides available only as
advanced configuration for nonstandard layouts. Management-suite logs remain a
separate app-owned data set.

## Consequences

Normal installation and Quick Start require fewer decisions, while advanced
operators retain flexibility. Code and documentation must clearly distinguish
Vein game logs from management logs.

See [config_reference.md](../config_reference.md) and
[management_logs.md](../management_logs.md).
