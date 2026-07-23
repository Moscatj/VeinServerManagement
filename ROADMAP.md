# Roadmap

This roadmap tracks practical maturity work for the Vein Server Management
Suite. It is intentionally lightweight: this is a personal, source-available
portfolio project, not a commercial product roadmap.

## Current Baseline

Released through `v2.11.0`:

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
- The GUI includes a server-config preview and guarded editor for allowlisted
  `Game.ini` and `Engine.ini` values. Secrets are masked, changes require a
  preview and confirmation, and every write is backed up and validated.
- Everyday Server Settings are organized into focused General, Access,
  Gameplay, Network, and Discord tabs with one shared review/apply workflow;
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
- The GUI provides read-only backup history across save, log, and configuration
  archives without exposing an insufficiently guarded restore action.
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
  protection can be removed without deleting the ZIP; this does not yet expose
  save loading.
- Selected archives have a read-only restore preview covering ZIP safety,
  manifest/save integrity, destination, server state, and the planned
  pre-restore safety backup. Restore execution remains unavailable.
- A tested guarded-restore backend now provides locking, journaling, a mandatory
  pinned safety backup, staged/hash-verified replacement, atomic activation, and
  automatic rollback. It is not connected to a GUI Restore action yet.
- Missing-save startup recovery is restored for normal and crash-monitor starts.
  It is independently configurable in Backup Policy, uses validated staged
  activation, never replaces an existing save, and blocks an established-server
  start when prior save archives exist but none can be verified.
- Read-only archive history shows total archive count and size, category count,
  oldest/newest dates, and category filtering without opening or modifying ZIPs.

## Near-Term Priorities

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
  `Docs/gui_modernization.md`, especially responsive layouts, logs/backups
  usability, diagnostics, and lifecycle integration hardening.
- Improve server-config editing with richer field descriptions, backup restore
  guidance, and broader validation summaries.
- Add a guided network-readiness workflow for Windows Firewall, router port
  forwarding, and external reachability checks without silently changing
  network configuration.

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
not a prerequisite for Linux support.

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

- Connect the guarded backend to an explicit final-confirmation workflow, add
  recovery guidance for interrupted operations, and only then expose Restore.
- Treat “Load Save” as a separate guarded workflow, not ordinary archive
  browsing or automatic retention.
- Require the server to be stopped and validate the selected archive/save before
  activation.
- Always create and verify a pre-load safety backup of the current active save.
- Stage the selected save, verify it, then replace the active file atomically;
  preserve the prior active save in history rather than deleting it.
- Show source, destination, timestamps, and consequences before confirmation,
  then validate the active save after loading and provide a clear rollback path.

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
than treating SteamCMD installs as the primary selector.

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
- Process matching and shutdown must target only the selected profile whenever
  possible, so two installed servers are not accidentally stopped together.
- Backups should be grouped by profile, not just by save filename.

SteamCMD should remain an implementation detail:

- One SteamCMD install can update multiple server roots by changing
  `force_install_dir`.
- Multiple SteamCMD installs may still be supported for operators who want
  isolated tool folders, but this should not be required for normal use.
- Server identity should come from the profile and server root, not from which
  SteamCMD executable updated it.

Open design questions:

- Whether concurrent multi-server hosting is supported in the first version, or
  whether the GUI initially allows multiple profiles but only one running server
  at a time.
- How to display per-profile monitor state without mixing runtime files.
- How much profile editing belongs in the installer versus the GUI.

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
