# Server Quick Start

Server Quick Start is the guided setup flow for new and existing server
operators. It builds a reviewable plan before writing the local management
config or guarded Vein server configuration files.

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

The backend can now apply the plan through guarded local writers. It writes the
local management config and delegates game config writes to the existing server
config editor, which creates backups and validates after writing.

If the selected server root does not exist yet, Quick Start writes only the
management config and skips `Game.ini` / `Engine.ini` writes. This prevents the
tool from creating fake dedicated-server folders before SteamCMD has installed
the server files.

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
2. Choose `New Server` or `Existing Server`.
   If the selected folder already contains a Vein executable, `Game.ini`, or
   `Engine.ini`, Quick Start automatically switches to Existing Server mode.
3. For an existing server, Quick Start first uses the resolved server root and
   executable candidates from the active YAML config and loads supported values
   automatically. Each path field has a `Browse…` button: Server root opens a
   folder picker and SteamCMD opens a file picker. Use `Load Existing Settings`
   after selecting a different installation. Loading reads `Game.ini` and
   `Engine.ini` in the background.
4. Fill in new-server values or edit the imported existing-server values.
5. Click `Build Preview`.
6. Review blocking errors, warnings, management config updates, and proposed
   game config edits.
7. Click `Apply Setup` to update the local management config.
8. If the selected server root exists, Quick Start also backs up and writes the
   proposed `Game.ini` / `Engine.ini` edits through the guarded editor path.

New Server mode produces a complete initial game configuration. Existing
Server mode imports supported non-secret settings and only proposes game-file
edits for fields changed after import. Existing passwords and Discord webhook
URLs are not loaded into the form and remain unchanged unless the user enters a
replacement. The password status explicitly reports whether an existing
password is set, not set, or has not been checked. Each Discord webhook reports
the same configured, not-configured, or unknown state. Show/Hide controls reveal
only newly entered replacements; they never expose passwords or webhook tokens
read from `Game.ini`. Changing the selected server root invalidates the import
and requires loading that server again before a preview can be applied.

New Server mode only accepts a missing or empty destination. A populated folder
is blocked, and a detected Vein installation is forced into Existing Server
mode so it cannot be unintentionally reconfigured as a new server.

Quick Start intentionally avoids writing `Config/config.example.yaml`; if an
example template is currently selected, Apply targets the local
`Config/config.yaml` path instead.

## Future Install Flow

The intended GUI flow is:

1. Choose app-managed or existing server location.
2. Choose app-managed or existing SteamCMD.
3. Enter required server identity and network fields.
4. Confirm save, log, runtime, and backup locations.
5. Review management config updates and INI diffs.
6. Run SteamCMD install/update when requested.
7. Apply only after explicit confirmation.
8. Re-run Server Preflight and refresh the Server Config view.

## Multi-Server Direction

Quick Start should evolve naturally into profile creation, but the first
implementation still targets the current single active server config. Future
profile support should let users create named server profiles while keeping
SteamCMD as an implementation detail rather than the identity of a server.
