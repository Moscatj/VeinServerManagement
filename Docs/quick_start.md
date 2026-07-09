# Server Quick Start

Server Quick Start is the planned guided setup flow for first-time operators.
The initial backend foundation is preview-only: it builds a proposed setup plan
without writing `Config/config.yaml`, `Game.ini`, or `Engine.ini`.

## Current Scope

`Controller/Tools/server_quickstart.py` creates a `QuickStartPlan` from user
answers such as:

- server root
- SteamCMD path
- server name and description
- public/private mode and password
- max players
- gameplay, Steam query, and HTTP API ports
- bind address, VAC setting, heartbeat interval, and `-log` launch preference
- save, log, runtime, and backup paths
- admin, super admin, and whitelist Steam IDs
- Discord in-game chat and admin report webhook URLs
- scoreboard badge visibility
- PvP console variable

The plan contains:

- `config_updates` for management-suite config sections.
- `server_config_edits` built with the guarded server config editor allowlist.
- `issues` for missing required fields or invalid values.
- `can_apply`, which is false when any blocking error is present.

The backend does not apply anything by itself. Future GUI work should show the
plan to the operator, preview diffs, then apply changes through the existing
safe config writer and server config editor paths.

The GUI now includes a preview-only Server Quick Start view. It collects the
same first-run fields and shows a copyable plan, but it intentionally does not
write files yet.

## Safety Model

Quick Start must preserve the same write boundaries as the rest of the suite:

- Management config changes target the local app config only.
- Game config writes are limited to `Game.ini` and `Engine.ini`.
- Game config writes must use the existing backup, diff, atomic write, and
  validation path from `Controller/Tools/server_config_editor.py`.
- The flow must never edit saves, logs, binaries, content files, or SteamCMD
  files directly.
- Missing server files should be reported as setup/preflight warnings, not
  silently created outside the app-managed layout.
- The HTTP API should be treated as local/private by default because the Vein
  developer documentation describes it as unauthenticated.
- Environment-backed Discord webhooks remain preferred for management-suite
  notifications, but Vein's in-game chat integration requires the actual
  webhook URL in `Game.ini`.

## Reference Mapping

The local `Reference/` PDFs are not tracked in Git, but the quick-start planner
is aligned with their setup guidance:

- SteamCMD installs or updates app `2131400` into the selected server root.
- Windows server files are expected under the selected install directory, with
  the executable below `Vein/Binaries/Win64/`.
- UDP `27015` is the default Steam query port and UDP `7777` is the default
  gameplay port.
- Launch-time config uses `-QueryPort`, `-Port`, `-multihome`, and `-log`.
- `Game.ini` owns server identity, public visibility, password, max players,
  admin lists, whitelist, VAC, query/game/HTTP ports, and special
  `Vein.ServerSettings` entries.
- `Engine.ini` owns console variables such as PvP and other gameplay tuning.

## Current GUI Flow

1. Open `Quick Start` from the left navigation.
2. Fill in the first-run fields.
3. Click `Build Preview`.
4. Review blocking errors, warnings, management config updates, and proposed
   game config edits.

## Future Apply Flow

The intended GUI flow is:

1. Choose app-managed or existing server location.
2. Choose app-managed or existing SteamCMD.
3. Enter required server identity and network fields.
4. Confirm save, log, runtime, and backup locations.
5. Review management config updates and INI diffs.
6. Apply only after explicit confirmation.
7. Re-run Server Preflight and refresh the Server Config view.

## Multi-Server Direction

Quick Start should evolve naturally into profile creation, but the first
implementation still targets the current single active server config. Future
profile support should let users create named server profiles while keeping
SteamCMD as an implementation detail rather than the identity of a server.
