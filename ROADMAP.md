# Roadmap

This roadmap tracks practical maturity work for the Vein Server Management
Suite. It is intentionally lightweight: this is a personal, source-available
portfolio project, and the roadmap is a direction rather than a delivery or
support commitment.

## Current Baseline

Released through `v2.12.0`:

- Public source hygiene baseline.
- Sanitized config examples and documentation.
- Non-commercial source-available license.
- GitHub Actions CI for tests, diagnostics, coverage, and marker scanning.
- Unit test foundation for config, process helpers, runtime state, backups,
  management logs, and API helpers.
- AI assistant rules for safe repository work, testing, and release impact.
- Public config safety improvements: local `Config/config.yaml` is ignored,
  the tracked example config is used for CI, and Steam updates are disabled by
  default until the operator configures SteamCMD.
- Packaged installer releases are published through GitHub Releases with
  versioned installer assets and release notes.
- Packaged installs support an app-managed default layout with `SteamCMD\` and
  `Server\` under the app folder, while still allowing existing external server
  and SteamCMD paths.
- The installer supports intentional fresh, side-by-side, update/repair, and
  uninstall paths. It preserves local state during maintenance, reuses existing
  server/SteamCMD locations, and can reinstall a missing managed server.
- SteamCMD operations show live download/validation progress, initialize a new
  SteamCMD copy before use, retry once automatically, and retain diagnostic
  logs. The current Inno Setup operation is blocking and therefore explicitly
  non-cancellable; interrupted work resumes through Update/Repair.
- Uninstall cleanup stops management monitors/server processes and removes
  transient app-owned directories. Server data, config, and backups require
  explicit deletion choices.
- The management suite now includes read-only diagnostics for dedicated server
  layout and key Vein `Game.ini` / `Engine.ini` settings.
- The GUI dashboard surfaces a read-only server preflight summary so operators
  can spot missing files or mismatched ports before starting the server.
- The GUI includes guarded editors for allowlisted `Game.ini` and `Engine.ini`
  values. Routine forms generate their old-to-new review from Apply; technical
  edits retain explicit diffs. Secrets are masked and every write is backed up
  and validated.
- Everyday Server Settings are organized into focused General, Access,
  Gameplay, Network, and Discord tabs with one shared Apply-driven review;
  the allowlisted technical table remains available under Advanced Settings.
- Server Setup routes new and installer-provisioned servers through guided First
  Setup, connects unregistered existing servers compactly, and sends configured
  servers to guarded everyday Server Settings,
  including existing-install detection and protected secret replacement fields.
- Packaged lifecycle and monitor commands run through `VeinTools.exe`; normal
  users do not need Python. Log and save locations derive from the selected
  server root unless an advanced override is configured.
- CI installs the packaged application in isolation and verifies server start,
  duplicate-start protection, log/crash monitors, live-log attachment,
  restart, stop, runtime cleanup, and uninstall without source Python.
- Subsystem ownership, documentation/version consistency, source hygiene, and
  batch-wrapper references are validated automatically. Obsolete Continue,
  WebAdmin, wrapper, and generated-spec artifacts have been retired.
- The GUI now uses one task-oriented workspace with a state-aware primary
  server action, an At a Glance health summary, persistent startup progress,
  consolidated logs, and clearer monitor status.
- Quick Start now distinguishes app notifications from VEIN game-chat and
  admin-report webhooks, while lifecycle state remains accurate through
  joinable readiness and controlled monitor shutdown.
- The GUI provides backup history across save, log, and configuration archives
  with guarded restore available for validated save backups.
- The Backups page provides guarded global, Autosave, Crash, Shutdown, and
  default count/age cleanup controls. Cleanup can be disabled or use either
  rule independently; Apply backs up and validates config and does not
  immediately delete existing archives.
- Automatic cleanup protects a configurable minimum of the newest archives in
  every backup category (three by default), preserving rollback points after
  long server inactivity or a newly corrupted save.
- Operators can make existing archives into restore points or create new
  labeled restore points with optional notes. Restore points are filterable and
  excluded from automatic age/count cleanup. Labels/notes can be edited, and
  protection can be removed without deleting the ZIP.
- Selected archives have a read-only restore preview covering ZIP safety,
  manifest/save integrity, destination, and server state. Operators can continue
  through explicit final confirmation into guarded restore only when the server
  is stopped and the current save can first be protected.
- A tested guarded-restore backend now provides locking, journaling, a mandatory
  pinned safety backup, staged/hash-verified replacement, atomic activation, and
  automatic rollback. The Backups GUI delegates execution to this shared engine
  on a background worker and leaves the server stopped afterward.
- Restore-journal status is evaluated during backup-history refresh. Routine
  completed state stays out of the way, while active, safely aborted, rolled-back,
  interrupted, unreadable, and rollback-failed operations receive distinct
  guidance with preserved safety and recovery artifact paths.
- Missing-save startup recovery is restored for normal and crash-monitor starts.
  It is independently configurable in Backup Policy, uses validated staged
  activation, never replaces an existing save, and blocks an established-server
  start when prior save archives exist but none can be verified.
- Read-only archive history shows total archive count and size, category count,
  oldest/newest dates, and category filtering without opening or modifying ZIPs.

## Product Direction

Vein Server Management Suite is **local-first and VEIN-specific**. Its immediate
job is to make a process that is normally intimidating to a casual host feel
guided, understandable, and recoverable. Local operation is not a temporary
step toward a hosted-only product: the application should continue to work
without an account, cloud service, public management port, or permanent Internet
connection beyond operator-requested Steam and update workflows.

The primary user is one person in a friend group who has a capable Windows PC
and wants to keep a private shared world available even when they are not
playing or near the machine. They should not need to become a server
administrator, maintain fragile scripts, pay a hosting provider, or ask friends
to wait for them to recover every crash. Discord is the shared community surface
for this use case: game chat and events can reach the group, while application
notifications keep the host informed about server health and recovery.

The product north star is: **after guided setup, a friend-group server remains
available and recovers safely with minimal host intervention.** Product and
stability decisions should improve observable outcomes such as time to first
successful join, unattended availability, recovery after a crash, gameplay lost
after a save failure, false or repeated restarts, clarity of incident history,
and the effort required to restore or hand the world to another trusted host.

Development should progress in four ordered stages:

1. **Harden local single-server hosting.** Finish the approachable Windows
   installer, first-run guidance, diagnostics, lifecycle reliability, backup and
   restore safety, configuration help, host-handoff foundations, and regression
   coverage needed for a casual operator to host confidently.
2. **Expand to local multi-server hosting.** Introduce named, isolated server
   profiles and safe server selection first. Then permit concurrent servers and
   batch actions only after ports, processes, runtime state, logs, backups, and
   lifecycle controls are demonstrably profile-scoped.
3. **Add native Linux and WSL2 support.** Carry the hardened local backend and
   profile model to Linux rather than maintaining a separate reduced product.
4. **Add remote and commercial-grade management capabilities.** Build secure
   headless operation, authenticated remote administration, roles, audit trails,
   richer automation, off-machine backups, and fleet-oriented visibility on top
   of the same local control layer.

Throughout every stage:

- preserve fully functional offline/local administration;
- keep the GUI, CLI, future service/API, and automation paths on one guarded
  control layer;
- prefer deep VEIN-aware safety over generic file/process buttons;
- treat Discord integration as an optional, privacy-conscious bridge between
  the running world, the friend group, and the host—not merely as a diagnostic
  webhook or a substitute for guarded management controls;
- keep remote access opt-in and closed by default;
- do not weaken save, backup, restore, shutdown, or secret-handling safeguards
  to gain multi-server or remote convenience;
- treat datacenter networking, DDoS mitigation, redundant hardware, and support
  operations as hosting-provider capabilities that the app can diagnose or
  integrate with, not capabilities the app itself can promise.

## Near-Term Priorities

- Keep the near-term release focus on local Windows hosting: reliability,
  efficiency, approachable language, safe defaults, and clear recovery paths for
  casual hosts remain more important than remote or fleet-management features.
- Add current GUI and installer screenshots to the README without making the
  landing page difficult to scan.
- Keep GitHub Release pages populated with meaningful release notes and
  versioned installer artifacts.
- Maintain the aggregate required CI gate on `main`, including Python 3.11/3.12
  compatibility and path-aware installer compilation, without blocking the
  separate tag-driven release workflow.
- Continue focused unit coverage for non-GUI controller and Tools modules.
- Continue clean-machine installer tests for fresh install, side-by-side
  install, update/repair, missing-server reinstall, uninstall, and interrupted
  SteamCMD recovery.
- Add an in-app first-run checklist that connects installer results, Quick
  Start, preflight, firewall/router guidance, and the first successful launch.
- Complete the remaining phased GUI modernization described in
  `Docs/gui_modernization.md`, especially responsive layouts, log filtering,
  diagnostics, and lifecycle integration hardening.
- Improve server-config editing with richer field descriptions and broader
  validation summaries.
- Add a guided network-readiness workflow for Windows Firewall, router port
  forwarding, and external reachability checks without silently changing
  network configuration.
- Prepare the configuration, runtime-state, lifecycle, backup, monitoring, and
  GUI controller boundaries for named server profiles without prematurely
  exposing concurrent hosting.

## Installer And Binary Distribution Goals

Target user experience:

- Users who only want to run the suite download the versioned
  `VeinServerManagement-Setup-vX.Y.Z.exe` from GitHub Releases.
- The installer places `VeinManager.exe` and `VeinTools.exe` on disk, creates
  shortcuts, and stages a local `Config/config.yaml` from the public template.
- Users do not need to clone the repository or install Python for normal use.
- Developers still clone the repo when they want tests, source changes, or local
  packaging builds.

Ongoing installer hardening:

- Keep `Scripts\BuildInstaller.bat` as the canonical local build command.
- Build `VeinManager.exe` and `VeinTools.exe` from the current tagged source.
- Publish generated binaries as GitHub Release artifacts, not committed files.
- Keep packaging tests that confirm the staged bundle contains the GUI, CLI,
  docs, required runtime helpers, and sanitized config.
- Validate a fresh installer run on a clean Windows profile or VM before major
  public releases.
- Future code-signing hardening:
  - Sign `VeinManager.exe`, `VeinTools.exe`, and the final installer before
    publishing release assets.
  - Prefer a CI-compatible signing service such as Azure Artifact Signing /
    Trusted Signing when the project is ready for the identity validation and
    operating cost.
  - Timestamp signatures and verify them in CI before release publication.
  - Publish SHA256 checksums and the expected publisher name with each release.

## Native Linux And WSL2 Support Goals

Native Ubuntu/Debian Linux and Ubuntu hosted by WSL2 are both first-class
targets. The same Linux backend should run the VEIN dedicated server and the
management suite without requiring Windows APIs. WSL2 is one deployment option,
not a prerequisite for Linux support. This stage begins after the local Windows
workflow and profile-scoped multi-server foundation are stable enough to carry
across platforms without duplicating lifecycle or backup behavior.

Native Linux release model:

- Every supported release publishes versioned Linux assets through the same
  GitHub Release as the Windows installer.
- The initial package target is an x86-64 Debian/Ubuntu `.deb`, accompanied by a
  portable `.tar.gz` fallback and SHA256 checksums.
- The Linux installer installs the management GUI and CLI, then offers an
  explicit first-run flow to install/reuse Linux SteamCMD and download/update
  VEIN Dedicated Server app `2131400` into an operator-selected server root.
- VEIN binaries are downloaded from Steam by SteamCMD and are never bundled in
  this repository or management package.
- Headless Linux hosts can use the CLI and `systemd` services without installing
  or launching the desktop GUI.
- Package uninstall preserves server files, saves, config, and backups by
  default, with the same explicit deletion safeguards as Windows.

Target deployment model:

- Windows remains the licensed host operating system.
- WSL2 runs a supported Linux distribution, initially Ubuntu LTS.
- SteamCMD for Linux installs the VEIN Linux dedicated-server depot inside the
  distribution's Linux filesystem.
- The management backend, monitors, runtime state, backups, and server process
  run inside Linux rather than invoking Windows executables through WSL.
- The GUI may initially run through WSLg; a later remote-control design may let
  a Windows GUI manage a Linux/WSL backend over an authenticated local API.
- `systemd` units manage the server and long-running monitor processes.
- WSL mirrored networking is the preferred Windows 11 configuration, with
  explicit Hyper-V/Windows firewall rules for game, query, and management ports.

Required portability work:

- Introduce platform adapters for process discovery, process-tree shutdown,
  service control, file opening, and console visibility.
- Replace `taskkill`, `tasklist`, PowerShell/WMI, `.bat` wrappers, and
  Windows-only creation flags with Linux equivalents where appropriate.
- Support `steamcmd.sh`, Linux depot selection, and Linux executable discovery.
- Detect and validate the actual Linux server executable and Unreal config
  directory instead of assuming `Binaries/Win64` and `WindowsServer`.
- Add shell entrypoints and reviewed `systemd` service templates.
- Add Linux/WSL-aware health checks, Quick Start choices, and path defaults.
- Add Ubuntu CI coverage and clean WSL2 installation testing.
- Add a tag-driven Linux release workflow that builds, tests, checksums, and
  attaches `.deb` and `.tar.gz` assets to GitHub Releases alongside Windows.
- Test the installer and complete SteamCMD/VEIN setup on a clean native Ubuntu
  VM as well as WSL2.

See `Docs/linux_wsl_support.md` for the proposed phases, networking concerns,
licensing distinction, and acceptance criteria.

## Stability Goals

- Keep all server lifecycle actions routed through shared Tools modules.
- Preserve safe shutdown markers and backup behavior.
- Avoid writes to the external Vein game install except supported save-copy
  backup operations, SteamCMD install/update flows, and the guarded
  `Game.ini` / `Engine.ini` editor described below.
- Keep CI passing before merges or releases.
- Add regression tests for bug fixes when practical.
- Keep read-only `health-check` and `server-config-check` useful as release and
  first-run validation gates.

## Game Config Management

The guarded editor and Quick Start now edit selected Vein dedicated server
settings for operators who do not want to hand-edit Unreal INI files.

Implemented safety contract:

- Read, preview, validate, and write only:
  - `Vein\Saved\Config\WindowsServer\Game.ini`
  - `Vein\Saved\Config\WindowsServer\Engine.ini`
- Cover documented settings such as server name, description, public/private
  visibility, admin Steam IDs, max players, gameplay/query/HTTP ports, Discord
  chat webhooks, whitelist entries, and common console variables.
- Create a timestamped backup under `Backups\ConfigEdits\` before every write.
- Show a clear preview/diff before saving changes.
- Re-run validation after writing and surface any mismatches in the GUI.

Next improvements:

- Add richer per-setting descriptions and context where operators need it.
- Make backup discovery and operator-driven restore easier.
- Expand the allowlist only when a setting is documented and can be validated.

Out of scope for the guarded configuration editor:

- Editing saves, logs, binaries, content files, or arbitrary Steam/game files.
- Silent automatic rewrites during startup.
- Exposing the unauthenticated Vein HTTP API publicly without an explicit
  operator-controlled intermediary.

## Product Polish Goals

The approved phased GUI plan is documented in `Docs/gui_modernization.md`.

- Make GUI state and process status easier to scan.
- Improve local setup documentation for first-time users.
- Add clearer troubleshooting guidance for SteamCMD, Python, config paths, and
  Discord webhook setup.
- Package a cleaner Windows launch/install workflow with downloadable release
  artifacts.
- Add first-run diagnostics that make installed version, config path, server
  root, and validation status easy to verify.

### Discord And Friend-Group Connection

Discord should make a privately hosted world feel present and understandable
when nobody is sitting at the server PC. It remains optional, and local hosting
must work fully without it.

Current foundations include distinct configuration for application
notifications, VEIN game chat, and VEIN admin reports, plus log monitoring that
can recognize server health and player events. Future improvements should:

- make each Discord destination and message category easy to understand, test,
  disable, and route without exposing webhook URLs;
- deliver useful lifecycle and recovery outcomes, including whether an
  automatic restart or backup succeeded, instead of sending noisy raw logs;
- turn supported player and in-game events into opt-in, rate-limited community
  updates with clear provenance and sensible grouping;
- provide quiet hours, severity controls, event filters, and summaries so an
  unstable server cannot flood a group or repeatedly mention members;
- keep secrets, passwords, private paths, and sensitive diagnostic details out
  of messages, previews, exports, logs, and test output;
- keep all automated tests and validation isolated from real Discord network
  messages; and
- scope destinations and event preferences per profile when multi-server
  hosting arrives.

### Backup Policy And Save Management

The long-term backup experience should let operators balance rollback safety
against storage use without hand-editing YAML.

- Provide a global backup enable switch plus individual controls for manual,
  startup, shutdown, player login/logout, autosave, crash, and scheduled backup
  triggers where the underlying event is supported reliably.
- Expand the implemented default count/age cleanup rules into optional
  per-category policies.
- Show estimated/current storage use, archive counts, oldest/newest dates, and a
  preview of what the selected retention policy would prune.
- Include implemented restore points in cleanup previews and storage guidance.
- Keep profile backup roots and retention policies isolated when multi-server
  profiles are introduced.

A future Save Library should make rollback and switching worlds simple while
remaining non-destructive:

- Present active saves, backup archives, and restore points as clearly named
  library entries with timestamps, labels, notes, and validation state.
- Add guarded import, export, duplication, and world-switching actions on top of
  the implemented restore engine rather than introducing a second write path.
- Preserve the current stopped-server, validated-source, pre-load safety backup,
  staged activation, post-write verification, and rollback guarantees.
- Make branches and intentional rollback points easy to distinguish from
  automatic operational backups.
- Keep Load Save separate from automatic retention so selecting or switching a
  world never silently changes cleanup policy.

### Host Handoff And World Portability

A friend group should not lose access to its world when the original host no
longer wants or is able to run the server. A future guided handoff workflow
should let another trusted friend install the suite, prepare a compatible Vein
server, and import the shared world without either person manually reconstructing
paths and configuration.

Build this on the Save Library and guarded restore engine rather than adding an
unverified file-copy path:

1. Create a portable export only from a stopped server or a validated backup.
   Leave the source save and its backup history untouched.
2. Include a versioned manifest, content hashes, world metadata, relevant Vein
   version information when available, and an explicit inventory of the files
   in the package.
3. Offer a separately reviewed set of portable, non-secret server settings.
   Exclude webhook URLs, passwords, tokens, local paths, runtime markers, logs,
   SteamCMD, server binaries, and machine-specific state by default.
4. On the receiving machine, preview compatibility warnings, destination paths,
   port or profile conflicts, omitted settings, and every planned write before
   import. Do not claim to convert saves between incompatible game versions.
5. Protect any existing destination world, stage and hash-verify the imported
   world, activate it atomically, verify it after activation, and roll back on
   failure using the same guarantees as guarded restore.
6. Produce a checksum and clear transfer instructions while letting friends
   choose how they exchange the package. Host handoff must not require a project
   account, project-operated cloud storage, or a public management endpoint.
7. Reuse the same portable format for future profile import/export so migration
   between friends, machines, Windows and Linux does not become a separate
   lifecycle implementation.

The first implementation slice should be an offline export/import planner and
manifest validator exercised entirely in temporary directories. GUI transfer
convenience and any optional cloud destination come only after the local safety
contract is proven.

### Future Theme Customization

Theme customization is a long-term polish goal after the core workflows and
responsive page layouts are complete. It should build on semantic design tokens
rather than applying unrelated colors directly to individual controls.

- Provide tested Dark, Light, High Contrast, and System Default presets.
- Define semantic colors for window and panel surfaces, inputs, primary and
  secondary text, borders, selections, actions, and status states.
- Add a safe live preview with Apply, Cancel, and Restore Defaults so an
  unreadable selection never traps the operator.
- Validate minimum text contrast and reject unsafe foreground/background
  combinations.
- Start with preset and accent customization; consider broader color controls
  only after the semantic token model is stable.
- Store appearance preferences separately from VEIN server settings and keep
  server configuration exports free of GUI-only theme state.

## Multi-Server Hosting Goals

The current suite manages one configured Vein dedicated server at a time. A
future multi-server workflow should be based on named server profiles rather
than treating SteamCMD installs as the primary selector. This is the next major
local hosting expansion after single-server stabilization and comes before
native Linux and remote administration work.

Delivery should be intentionally staged:

1. Add multiple local profiles with one explicitly selected active profile and
   one running server at a time. Existing single-server configuration should
   migrate into a default profile without changing its server files or saves.
2. Prove that paths, ports, process discovery, runtime markers, monitors,
   backups, restore locks, logs, Steam maintenance, and Discord routing are
   isolated by profile.
3. Allow multiple concurrent local servers only after collision checks and
   targeted shutdown tests demonstrate that one profile cannot stop, overwrite,
   restore, or report state for another.
4. Add guarded batch actions such as Start Selected, Stop Selected, or Stop All,
   with per-profile results and explicit confirmation for broad lifecycle
   operations.

Target model:

- Add named profiles such as `Personal`, `Test`, or `Community PVE`.
- Each profile owns its own:
  - `server_root`
  - executable preference
  - game/query ports
  - save and log paths
  - runtime state directory
  - backup root and retention policy
  - Discord channel/webhook routing
  - Steam branch/update settings
- The GUI selects the active profile before start/stop/backup/monitor actions.
- Home and navigation make the selected profile unmistakable and show whether
  other profiles are stopped, starting, running, unhealthy, or awaiting setup.
- Process matching and shutdown must target only the selected profile, so two
  installed servers are never treated as one process group.
- Backups should be grouped by profile, not just by save filename.
- Port validation must reject unintended gameplay, query, HTTP API, or future
  management-port collisions before a second server starts.
- Profile duplication and export should copy management settings intentionally
  without silently duplicating or moving live saves, server binaries, secrets,
  or backup archives.

SteamCMD should remain an implementation detail:

- One SteamCMD install can update multiple server roots by changing
  `force_install_dir`.
- Multiple SteamCMD installs may still be supported for operators who want
  isolated tool folders, but this should not be required for normal use.
- Server identity should come from the profile and server root, not from which
  SteamCMD executable updated it.

Design constraints still to resolve:

- How the GUI summarizes per-profile monitor and player state without making the
  single-server workflow feel like a fleet dashboard.
- Which minimal profile selection belongs in the installer and which ongoing
  profile management belongs only in the application.
- Whether concurrency should have optional CPU/memory guidance before platform
  resource limits or container adapters exist.

## Remote And Commercial-Grade Management Goals

Remote administration begins only after local multi-server hosting and native
Linux are stable. It should extend the local product rather than replace it or
create a second lifecycle implementation.

Foundation:

- Separate the long-running management backend from desktop presentation behind
  a documented, versioned command/service boundary.
- Run a headless service that can manage profiles when no GUI user is signed in.
- Let the desktop GUI use the same service locally before opening that boundary
  to remote clients.
- Bind locally by default. Remote listening requires an explicit operator action,
  authenticated setup, encryption, and diagnostics that identify unsafe public
  exposure.

Administration and security:

- Add named administrators, least-privilege roles, revocable sessions or API
  credentials, and an audit trail for lifecycle, configuration, backup, restore,
  update, and profile actions.
- Protect secrets at rest and keep webhook, password, and token values out of
  logs, routine API responses, exports, and audit details.
- Add rate limits, bounded requests, secure defaults, upgrade compatibility, and
  recovery access that does not depend on the remote service being healthy.
- Keep the unauthenticated VEIN HTTP API private; never expose it merely because
  management access is enabled.

Operational capabilities worth adopting from mature general-purpose panels:

- Responsive remote status and emergency controls for desktop and mobile use.
- Scheduling for starts, controlled stops, restarts, Steam validation, backups,
  retention previews, announcements, and maintenance windows.
- Per-profile CPU, memory, disk, network, player, update, backup, and health
  visibility, with historical trends where the data is reliable.
- Off-machine backup destinations, transfer verification, restore testing, and
  clear reporting when local safety points are the only available recovery path.
- Optional platform resource limits or container adapters without making
  containers mandatory for casual local hosts.
- Provider-friendly unattended installation, configuration import/export, and
  health endpoints suitable for external monitoring.

Commercial-readiness considerations:

- Signed packages, checksums, reliable upgrades, supported migration paths, and
  clean-machine deployment tests are prerequisites for trust at broader scale.
- Regional hosting, public IPs, DDoS protection, redundant power/storage,
  hardware replacement, billing, and staffing remain responsibilities of a host
  or infrastructure provider rather than promises of the management suite.
- Before enabling paid hosting or other commercial deployment, define a clear
  licensing and support model consistent with the current non-commercial
  source-available license.

## Testing Goals

- Increase coverage around:
  - backup retention decisions
  - process lifecycle edge cases
  - log parsing and summarization
  - Steam update/version helper behavior
  - config validation and fallback behavior
  - server config validation and guarded INI write behavior
- Keep GUI testing focused on controller/helper seams unless a stable UI test
  harness is added later.

## Known Limitations

- The current release is Windows-only; Linux and WSL2 are roadmap targets.
- The actual Vein dedicated server is not included.
- GUI coverage is intentionally lower than backend/helper coverage.
- Full integration tests require a local Vein server install and are not part
  of normal CI.
- Commercial use requires a separate written license from the maintainer.
