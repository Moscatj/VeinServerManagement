# Changelog

All notable changes to this project will be documented here.

This project uses a lightweight versioning approach suitable for a personal source-available project. Dates use `YYYY-MM-DD`.

## Unreleased

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
