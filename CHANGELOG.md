# Changelog

All notable changes to this project will be documented here.

This project uses a lightweight versioning approach suitable for a personal source-available project. Dates use `YYYY-MM-DD`.

## Unreleased

- Clarified installer usage and roadmap, added packaging requirements, and made installer builds derive their version from the release tag.
- Fixed Inno Setup compilation issues and tightened packaged bundle staging to exclude local backups, legacy account state, and development-only scripts.
- Fixed installed app launch by granting modify permissions to installer-owned config/runtime folders and preventing packaged CLI subcommands from inheriting wrapper arguments.
- Improved installer onboarding by always collecting the Vein dedicated server root and writing installed config paths for both SteamCMD and existing-server installs.
- Kept installer-managed SteamCMD files separate from the dedicated server root and added validation for accidentally selecting the inner `Vein` folder.
- Moved Inno Setup's generated uninstaller files into an `Uninstall` subfolder and set the uninstall display icon to the GUI executable.
- Added uninstall cleanup that stops log/crash monitors and performs a controlled server shutdown when a Vein server process is still running.
- Added uninstall safeguards that preserve external dedicated server folders and require an explicit save-loss warning prompt before deleting app-managed server files.

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
