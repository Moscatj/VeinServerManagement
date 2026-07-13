# Server Quick Start

Server Quick Start is the guided setup flow for new and existing server
operators. It builds a reviewable plan before writing the local management
config or guarded Vein server configuration files.

## Current Scope

`Controller/Tools/server_quickstart.py` creates a `QuickStartPlan` from user
answers such as:

- server root
- the automatically derived Vein SaveGames directory, with an optional advanced override
- SteamCMD path
- server name and description
- public/private mode and password
- max players
- gameplay, Steam query, and HTTP API ports
- bind address, VAC setting, heartbeat interval, and `-log` launch preference
- save, runtime, management-log, and backup paths
- the automatically derived Vein Game Log, with an optional advanced override
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
- The management app launches
  `Vein/Binaries/Win64/VeinServer-Win64-Test.exe` directly when it exists.
  The adjacent small `VeinServer.exe` is treated as a bootstrap/discovery
  executable because launching it in the SteamCMD layout can duplicate the
  `Vein/Binaries/Win64` path.
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
   The read-only `Vein SaveGames folder` follows Server root as
   `<server root>/Vein/Saved/SaveGames`. Expand its advanced override only for
   a nonstandard installation; backups then read from that custom directory.
   The read-only `Monitored Vein game log` field follows Server root as
   `<server root>/Vein/Saved/Logs/Vein.log`. Expand the advanced override only
   for a nonstandard installation; the selected file is then shared by server
   launch and monitoring.
5. Click `Build Preview`.
6. Review blocking errors, warnings, management config updates, and proposed
   game config edits.
7. Click `Apply Setup` to update the local management config.
8. If the selected server root exists, Quick Start also backs up and writes the
   proposed `Game.ini` / `Engine.ini` edits through the guarded editor path.

If the active configuration does not resolve to a supported Vein server
executable, the command bar disables Start, Restart, and both monitor Start
actions. A visible `Set Up Serverâ€¦` action opens Quick Start; stop actions only
become available for processes that are actually running. The Quick Start page
uses scrollbars and minimum control heights on smaller displays instead of
compressing fields into unreadable rows.

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

## Network Readiness

Selecting `List server publicly` configures Vein's public-server setting; it
does not by itself make the computer reachable from the internet. With the
default Quick Start values, the host normally needs inbound UDP access for:

- gameplay: `7777`
- Steam query/discovery: `27015`

Windows Firewall must allow the selected server executable or these selected
UDP ports. The internet router must forward the same UDP ports to the server
computer's stable LAN address. Router interfaces differ, carrier-grade NAT may
prevent inbound hosting, and the app cannot safely automate arbitrary router
configuration. Do not forward the HTTP API port (`8080` by default) unless the
operator intentionally secures and exposes that service.

The current GUI displays this guidance but does not yet create firewall rules,
configure the router, reserve a LAN address, or perform an external reachability
test. Those checks belong in the planned multi-step Network Readiness wizard.

Quick Start intentionally avoids writing `Config/config.example.yaml`; if an
example template is currently selected, Apply targets the local
`Config/config.yaml` path instead.

## Future Install Flow

The intended GUI flow is:

1. Choose app-managed or existing server location.
2. Choose app-managed or existing SteamCMD.
3. Enter required server identity and network fields.
4. Confirm save, runtime, management-log, and backup locations. The Vein Game
   Log is derived automatically unless an advanced override is required.
5. Review management config updates and INI diffs.
6. Run SteamCMD install/update when requested.
7. Apply only after explicit confirmation.
8. Re-run Server Preflight and refresh the Server Config view.

## Multi-Server Direction

Quick Start should evolve naturally into profile creation, but the first
implementation still targets the current single active server config. Future
profile support should let users create named server profiles while keeping
SteamCMD as an implementation detail rather than the identity of a server.
