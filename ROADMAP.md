# Roadmap

This roadmap tracks practical maturity work for the Vein Server Management
Suite. It is intentionally lightweight: this is a personal, source-available
portfolio project, not a commercial product roadmap.

## Current Baseline

Released through `v2.3.4`:

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
