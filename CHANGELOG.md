# Changelog

All notable changes to this project will be documented here.

This project uses a lightweight versioning approach suitable for a personal source-available project. Dates use `YYYY-MM-DD`.

## Unreleased

- Fixed clean-install live logging so the GUI begins watching before the game
  creates its first `Vein.log`, then attaches automatically when the file
  appears and reopens logs that are replaced or truncated.
- Hardened log discovery across configured and app-managed server paths, added
  packaged monitor stdout diagnostics and actionable runtime state, and made
  the Home dashboard distinguish waiting, tailing, offline, and read-error
  states.
- Aligned the log monitor's graceful-stop flag with the GUI and lifecycle
  controllers. Packaged monitoring continues to run through bundled
  `VeinTools.exe` without requiring Python or developer dependencies.
- Made installer builds fail when the selected Python/PyInstaller command is
  unavailable or exits nonzero, preventing an old staged bundle from being
  mislabeled as a successful new build.
- Simplified game-log configuration to one canonical Vein Game Log derived
  from the selected server root, with a hidden advanced file override shared
  by server launch and monitoring. Quick Start removes obsolete legacy log
  keys when saving while older configs remain readable.
- Removed the redundant installer log-folder prompt and clarified the GUI tabs
  that show Vein Game Log output, management logs, and runtime monitor status.
- Removed the installer SaveGames prompt and now derives Vein's world-save
  directory from Server root. Quick Start shows the resolved directory and
  keeps custom SaveGames locations behind an advanced folder override.
- Added installer-driven in-place upgrade and repair detection. Existing local
  config and server data are preserved, prior server/SteamCMD paths are reused,
  and optional SteamCMD server repair/update runs only after the canonical
  controlled shutdown succeeds.
- Refined installer onboarding around an explicit first-step goal. Detected
  installations now default to a streamlined app-only update/repair that leaves
  server configuration untouched, while a separate intentional workflow can
  install a new server under a different root. Ready-page wording and subsequent
  questions follow the selected goal.
- Hardened the source-development GUI launcher so it deterministically selects
  a usable windowless Python runtime and captures failures that occur before the
  normal GUI logger starts. Silent bootstrap failures now produce an actionable
  dialog and a traceback under `Logs/gui/bootstrap/`.
- Fixed a native Windows GUI crash caused by overlapping background status
  workers reparsing YAML. Status polling now permits only one active worker,
  captures its small config snapshot before execution, and never invokes a YAML
  parser from the worker thread.

## 2.8.2 - 2026-07-11

- Made the dedicated runtime binary
  `Vein/Binaries/Win64/VeinServer-Win64-Test.exe` the explicit launch target
  when present, while retaining `VeinServer.exe` only for discovery and legacy
  fallback. This avoids the Unreal bootstrapper duplicating its relative path.
- Prevented duplicate server launches by detecting an existing Vein process
  before Steam updates, monitor startup, or executable launch; the GUI now
  reports that the server is already running instead of claiming a new launch.
- Distinguished unavailable SteamCMD from a true update failure, stopped
  retrying missing executables, and corrected SteamCMD beta/validate arguments
  so each option is passed as its own command argument.
- Added an in-installer Retry option when SteamCMD fails to download the Vein
  dedicated server, while preserving the diagnostic log paths and allowing the
  user to finish without server files.
- Disabled server and monitor start controls when no supported Vein executable
  is installed or selected, added a visible Quick Start setup action, and kept
  stop controls tied to actual running processes.
- Made Quick Start scrollable with minimum field and preview heights plus
  wrapped option rows so narrow or short windows cannot compress form text.
- Hardened packaged lifecycle control so explicit config selections override
  inherited values, server-stop failures produce captured diagnostics, and
  monitor start/stop exceptions surface actionable errors. Failed server starts
  now roll back spawned monitors, and packaged monitor-stop commands recognize
  frozen `VeinTools.exe` subcommands.
- Clarified packaged health checks so the CLI does not warn that PySide6 is
  absent when the GUI runtime is bundled separately in `VeinManager.exe`.
- Changed the Windows installer defaults to the recommended app-managed
  SteamCMD and dedicated-server installation path for novice operators.
- Added immediate Quick Start network-readiness guidance and detailed the
  planned firewall, router, and reachability wizard behavior.

## 2.8.1 - 2026-07-11

- Fixed a CI safety-scan false positive caused by diagnostic dialog labels being
  interpreted as a local drive path.

## 2.8.0 - 2026-07-11

- Added the phased GUI modernization plan and the first shared visual component
  foundation for consistent page headers, notices, status badges, and actions.
- Fixed dark-theme subtitle contrast and prevented Home dashboard cards and the
  global status message from being compressed into unreadable text.
- Fixed persisted log-monitor and player snapshots being presented as live when
  the server process is offline; offline now forces zero online players and
  labels cached details as last-known data.
- Fixed clean-machine packaged startup by routing GUI and monitor/restart helper
  launches through `VeinTools.exe` instead of requiring `py -3`, collecting all
  dynamic CLI modules in PyInstaller, detecting early server exits, and showing
  actionable GUI errors with captured output paths.
- Documented future native Linux and WSL2 support goals, including versioned
  GitHub `.deb` and portable Linux packages, guided SteamCMD/VEIN installation,
  an Ubuntu WSL2 deployment model, platform-portability phases, networking,
  services, validation criteria, and the WSL versus Windows-VM licensing
  distinction.

## 2.7.0 - 2026-07-10

- Added explicit New Server and Existing Server Quick Start modes. Existing
  servers automatically use the active YAML's resolved server path, can import
  supported non-secret INI settings, and only changed fields are included in
  the guarded apply preview.
- Hardened New Server mode so populated destinations are blocked and detected
  Vein installations automatically switch to Existing Server mode.
- Added folder and file pickers beside the Quick Start server-root and SteamCMD
  path fields so paths do not need to be typed manually.
- Added explicit existing-password status and a Show/Hide control for newly
  entered Quick Start replacement passwords without exposing stored passwords.
- Added matching configured-state indicators and Show/Hide controls for both
  Quick Start Discord webhook replacement fields without importing stored URLs.
- Kept configured `-log` launch arguments from restoring the visible log window
  during headless startup; the fallback launch still adds it when needed.

- Added a tested backend Server Quick Start planner that previews first-run
  management config updates and guarded `Game.ini` / `Engine.ini` edits without
  writing files.
- Expanded the Server Quick Start planner to cover developer-documented setup
  fields including bind address, VAC, heartbeat, whitelist, scoreboard badges,
  Discord chat webhooks, and HTTP API safety warnings.
- Added a preview-only GUI Server Quick Start view for entering first-run
  settings and reviewing generated management config updates and guarded
  `Game.ini` / `Engine.ini` edits before any apply workflow is exposed.
- Added a guarded Quick Start apply flow that writes local management config,
  skips game-config writes until the selected server root exists, and delegates
  `Game.ini` / `Engine.ini` changes to the existing backup, atomic write, and
  validation path.

## 2.6.0 - 2026-07-08

- Added read-only Vein server install/config diagnostics for expected executable files, Steam API DLLs, and documented `Game.ini` / `Engine.ini` settings.
- Added a GUI Server Preflight dashboard card that runs read-only server install/config validation on manual refresh and after config saves.
- Clarified server preflight severity by treating optional `Core.Log` guidance as `INFO` instead of a warning.
- Added a read-only GUI Server Config preview for key `Game.ini` and `Engine.ini` settings with secret masking.
- Expanded the Server Config preview to include all additional keys already present in the actual server config files.
- Added a tested backend edit engine for allowlisted `Game.ini` and `Engine.ini` changes with preview diffs, backups, atomic writes, and post-write validation.
- Added GUI controls to preview and explicitly apply allowlisted server config edits through the tested backup/diff/write path.
- Updated dedicated server launch arguments to use documented `-multihome` and `-Port` casing.
- Documented the future guarded Game.ini/Engine.ini editor exception with required preview, validation, and backup safeguards.

## 2.5.6 - 2026-07-08

- Added CI fixture directories for the app-managed server layout so health checks can validate a clean source checkout without requiring real dedicated server files.

## 2.5.5 - 2026-07-08

- Allowed config loading before the app-managed `Server\` folder exists so fresh installs and CI can run setup checks before the dedicated server is installed.

## 2.5.4 - 2026-07-08

- Aligned packaged default config paths with the app-managed `Server\` and `SteamCMD\` install layout and documented the fresh-install health-check flow.

## 2.5.3 - 2026-07-08

- Added uninstall prompts for removing local backups and config files so full uninstall can leave no app-owned folders behind.

## 2.5.2 - 2026-07-08

- Fixed clipped SteamCMD installer page helper text.

## 2.5.1 - 2026-07-07

- Fixed installer startup by avoiding `{app}` expansion before Inno Setup initializes the selected app directory.
- Added future code-signing and release checksum goals to the roadmap.
- Added release workflow enforcement that publishes GitHub Release notes from the matching `CHANGELOG.md` version section and documents meaningful annotated tag messages.

## 2.5.0 - 2026-07-07

- Clarified installer usage and roadmap, added packaging requirements, and made installer builds derive their version from the release tag.
- Fixed Inno Setup compilation issues and tightened packaged bundle staging to exclude local backups, legacy account state, and development-only scripts.
- Fixed installed app launch by granting modify permissions to installer-owned config/runtime folders and preventing packaged CLI subcommands from inheriting wrapper arguments.
- Improved installer onboarding by always collecting the Vein dedicated server root and writing installed config paths for both SteamCMD and existing-server installs.
- Kept installer-managed SteamCMD files separate from the dedicated server root and added validation for accidentally selecting the inner `Vein` folder.
- Moved Inno Setup's generated uninstaller files into an `Uninstall` subfolder and set the uninstall display icon to the GUI executable.
- Added uninstall cleanup that stops log/crash monitors and performs a controlled server shutdown when a Vein server process is still running.
- Added uninstall safeguards that preserve external dedicated server folders and require an explicit save-loss warning prompt before deleting app-managed server files.
- Documented the planned multi-server profile model for hosting multiple Vein server installs from one management suite.
- Updated GitHub Actions workflow dependencies to Node 24-compatible action versions.
- Added a tag-triggered GitHub Actions workflow that builds the Windows installer and publishes it as a GitHub Release asset.
- Fixed release installer builds so PyInstaller has the GUI/runtime dependencies, including PySide6, available during packaging.
- Hardened SteamCMD installer extraction by validating the downloaded archive and extracting to a temporary folder before copying `steamcmd.exe` into the app folder.
- Fixed SteamCMD extraction by letting the ZIP extractor create its temporary destination folder.
- Fixed SteamCMD installer PowerShell quoting so download and extraction paths are passed safely from Inno Setup.
- Captured installer-run SteamCMD output to `Logs\steamcmd-install.log` and included SteamCMD log paths in failure messages.
- Added the release version to generated installer filenames and GitHub Release assets.
- Made installer-run SteamCMD requests explicit for the Windows public branch and preserved installed config/logs when SteamCMD cannot download the dedicated server.
- Hid the blank SteamCMD console during installer-run server downloads and clarified that the SteamCMD step may take several minutes.
- Treated SteamCMD's "fully installed" output as a successful server install even if SteamCMD returns a misleading exit code.
- Included dynamically loaded CLI subcommands in packaged `VeinTools.exe` builds.
- Added a responsive GUI About dialog that shows the installed app version, runtime details, license, repository, and config path.
- Expanded installer defaults so full-package installs use app-managed `SteamCMD` and `Server` folders, while existing installs can reuse an external SteamCMD folder and override SaveGames/log paths.
- Cleaned up app-owned `Logs`, `Runtime`, and app-managed `SteamCMD` folders during uninstall while preserving server data and external installs.

## 2.3.4 - 2026-07-02

- Made `Config/config.yaml` local-only and kept `Config/config.example.yaml` as the tracked public template.
- Disabled Steam updates by default in the public example config until SteamCMD is configured.

## Earlier 2.3.x Changes

- Fixed GUI config-row edits for YAML files so saving a single setting does not rewrite `config.yaml` as JSON.
- Moved GUI log-monitor and crash-monitor stop waits off the Qt UI thread so monitor controls stay responsive.
- Moved GUI shutdown command execution off the Qt UI thread so server shutdown no longer makes the window appear unresponsive.
- Avoided comment-preserving YAML parsing in GUI runtime polling paths to prevent native YAML parser crashes during manual GUI testing.
- Clarified management-log documentation and kept `Logs/Archive` out of subsystem discovery.
- Added a read-only project health check command for config, dependency, path, executable, SteamCMD, and Discord webhook safety diagnostics.
- Added coverage strategy documentation and updated AI/contributor testing rules.
- Added a project roadmap and fixed the README CI badge repository URL.
- Added release process documentation and AI-assisted versioning rules.
- Added GitHub Actions CI for tests, coverage, diagnostics, and secret/local marker scanning.
- Added testing policy requiring unit tests for new behavior when practical.
- Sanitized public documentation, config defaults, metadata, and ignored local-sensitive files.
- Expanded unit coverage for config loading, runtime state, process helpers, management logs, backups, and API helpers.

## 2.2.0 - 2026-06-25

- Established public source release readiness baseline.
- Retired tracked local artifacts and config backups.
- Moved local API credentials to ignored environment files.
- Added coverage reporting through `Scripts/RunCoverage.bat`.
