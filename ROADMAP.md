# Roadmap

This roadmap tracks practical maturity work for the Vein Server Management
Suite. It is intentionally lightweight: this is a personal, source-available
portfolio project, not a commercial product roadmap.

## Current Baseline

Released through `v2.5.0`:

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

## Near-Term Priorities

- Improve README presentation with current GUI screenshots.
- Add GitHub Release pages with release notes and installer artifacts.
- Enable branch protection on `main` after release workflows are stable.
- Continue focused unit coverage for non-GUI controller and Tools modules.
- Review legacy modules and document what is retained for reference versus
  still supported.

## Installer And Binary Distribution Goals

Target user experience:

- Users who only want to run the suite download `VeinServerManagement-Setup.exe`
  from GitHub Releases.
- The installer places `VeinManager.exe` and `VeinTools.exe` on disk, creates
  shortcuts, and stages a local `Config/config.yaml` from the public template.
- Users do not need to clone the repository or install Python for normal use.
- Developers still clone the repo when they want tests, source changes, or local
  packaging builds.

Near-term installer hardening:

- Keep `Scripts\BuildInstaller.bat` as the canonical local build command.
- Build `VeinManager.exe` and `VeinTools.exe` from the current tagged source.
- Publish generated binaries as GitHub Release artifacts, not committed files.
- Add a packaging smoke test that confirms the staged bundle contains the GUI,
  CLI, docs, scripts, and sanitized config.
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

## Stability Goals

- Keep all server lifecycle actions routed through shared Tools modules.
- Preserve safe shutdown markers and backup behavior.
- Avoid writes to the external Vein game install except supported save-copy
  backup operations.
- Keep CI passing before merges or releases.
- Add regression tests for bug fixes when practical.

## Product Polish Goals

- Make GUI state and process status easier to scan.
- Improve local setup documentation for first-time users.
- Add clearer troubleshooting guidance for SteamCMD, Python, config paths, and
  Discord webhook setup.
- Package a cleaner Windows launch/install workflow with downloadable release
  artifacts.

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
- Keep GUI testing focused on controller/helper seams unless a stable UI test
  harness is added later.

## Known Limitations

- The project is Windows-focused.
- The actual Vein dedicated server is not included.
- GUI coverage is intentionally lower than backend/helper coverage.
- Full integration tests require a local Vein server install and are not part
  of normal CI.
- Commercial use requires a separate written license from the maintainer.
