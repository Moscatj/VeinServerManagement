# Server Quick Start

Server Quick Start is the guided setup flow for a new or not-yet-configured
server. Existing configured servers use the smaller Server Settings view for
everyday changes. Importing an existing unregistered server is a compact,
explicit connection step rather than a trip through the new-server wizard.

This unofficial management suite does not include the VEIN game. Players can
find the demo and purchase options on the
[official VEIN Steam page](https://store.steampowered.com/app/1857950/VEIN/).
The guided server workflow installs only the separate dedicated server files.

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
- three clearly separated Discord destinations:
  - App Notifications in `config.yaml` for startup, shutdown, crash, backup,
    player, and monitor messages sent by Vein Server Manager
  - VEIN Game Chat in `Game.ini`
  - VEIN Admin Reports in `Game.ini`
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
- App Notifications accepts either an `ENV:VARIABLE_NAME` reference or a
  literal Discord webhook URL. VEIN Game Chat and VEIN Admin Reports require
  literal URLs in `Game.ini`.
- A newly entered literal App Notifications webhook can be reused for either
  VEIN destination. Stored secrets are never loaded back into form fields, so
  reuse requires entering the replacement webhook during that Quick Start run.
- Blank replacement fields preserve existing webhook values. Copyable previews
  mask literal webhook URLs.

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

Setup classifies the selected root and active management config before choosing
a workflow. Finding an executable alone does not mean setup is complete.

| Detected state | Setup experience | Primary action |
| --- | --- | --- |
| New or missing server | Four-page new-server wizard | Install/configure the server |
| SteamCMD-installed server awaiting configuration | Same four-page wizard, starting at First Setup | Finish server setup |
| Existing server with meaningful INI settings but no setup record | Compact Location/import panel | Load, then Connect Existing Server |
| Existing configured server | No setup wizard | Open Server Settings |
| Completed setup whose binaries are missing | New/repair guidance | Repair the missing server |
| Conflicting root and completion record | Explicit workflow choice | Choose the intended server workflow |

For New Server and First Setup:

1. Open `Setup` from the left navigation.
2. On **Location**, confirm the server, SteamCMD, SaveGames, and game-log paths.
3. On **Identity & Access**, fill in server identity, password, gameplay, and
   Steam ID values.
   The read-only `Vein SaveGames folder` follows Server root as
   `<server root>/Vein/Saved/SaveGames`. Expand its advanced override only for
   a nonstandard installation; backups then read from that custom directory.
   The read-only `Monitored Vein game log` field follows Server root as
   `<server root>/Vein/Saved/Logs/Vein.log`. Expand the advanced override only
   for a nonstandard installation; the selected file is then shared by server
   launch and monitoring.
4. On **Network & Integrations**, review ports, public/API choices, and the
   three separate Discord webhook destinations.
5. Use **Back** and **Next** to revisit earlier pages. Entered values and
   protected replacements are preserved.
6. On **Review & Apply**, click `Build Preview`.
7. Review blocking errors, warnings, management config updates, and proposed
   game config edits.
8. Click `Apply Setup` to update the local management config.
9. If the selected server root exists, Quick Start also backs up and writes the
   proposed `Game.ini` / `Engine.ini` edits through the guarded editor path.
10. After setup is confirmed complete, the GUI automatically opens Server
    Settings for everyday guarded updates. If setup remains incomplete, the
    wizard stays open.

For an existing unregistered server, select its root, load its settings, and
choose `Connect Existing Server`. This records the management paths and setup
state while preserving current game settings. Future edits belong in Server
Settings, which retains the guarded preview, backup, write, and validation path.

If the active configuration does not resolve to a supported Vein server
executable, the command bar disables Start, Restart, and both monitor Start
actions. A visible `Set Up Server…` action opens Quick Start; stop actions only
become available for processes that are actually running. The Quick Start page
uses scrollbars and minimum control heights on smaller displays instead of
compressing fields into unreadable rows.

New Server and First Setup produce a complete initial game configuration.
Existing import reads supported non-secret settings only. Existing passwords
and Discord webhook URLs are never loaded into fields or exposed in the compact
connection flow.

New Server accepts a missing or empty destination. First Setup additionally
accepts the executable installed by the installer because its durable setup
record says configuration is still incomplete. Other populated folders remain
blocked from new-server apply.

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

## Multi-Server Direction

Quick Start should evolve naturally into profile creation, but the first
implementation still targets the current single active server config. Future
profile support should let users create named server profiles while keeping
SteamCMD as an implementation detail rather than the identity of a server.
