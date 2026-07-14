# 0004 — Prefer App-Managed SteamCMD

**Status:** Accepted

## Context

SteamCMD is portable, but requiring novice operators to locate and maintain a
separate copy made clean installation unreliable. Advanced operators may already
have a shared SteamCMD installation.

## Decision

Fresh packaged installs default to an app-managed `SteamCMD` directory and an
app-managed `Server` root. The installer may connect to existing SteamCMD or
server locations when the operator deliberately chooses that advanced path.
Maintenance reuses the configured location instead of asking repeatedly.

## Consequences

The recommended path is predictable and self-contained. Uninstall and repair
logic must preserve server data by default and clearly distinguish app-owned
tools from operator-owned external installations.

See [packaging_overview.md](../packaging_overview.md) and
[quick_start.md](../quick_start.md).
