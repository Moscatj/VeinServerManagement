# Security Policy

## Supported Versions

This is a personal source-available project. Security fixes are made on the current `main` branch.

## Reporting A Vulnerability

Please do not open a public issue for a suspected secret leak, credential exposure, or security-sensitive bug.

Use GitHub's private vulnerability reporting feature if it is enabled for the repository. If private reporting is not available, open a minimal public issue that asks for a maintainer contact path without including exploit details, credentials, logs, or private server information.

## Secret Hygiene

Never commit:

- API keys or webhooks.
- `.env` files.
- Local config overrides.
- Runtime state, logs, backups, save files, or user-account files.

If a secret is committed accidentally, revoke it immediately. Removing it from the current tree does not remove it from Git history.

## Runtime Safety

Source-development game installs should remain outside this repository.
Packaged installs may maintain an app-managed server, and the installer may run
SteamCMD to install, update, validate, or repair the operator-selected server
root.

Outside SteamCMD maintenance, game data is read-only except for two narrow,
operator-initiated workflows:

- backups copy save data into the management suite's backup area;
- the guarded server-config editor may update only `Game.ini` and `Engine.ini`
  after showing a preview, creating a timestamped backup, and validating the
  result.

The suite must never silently edit or delete saves, game logs, binaries, or
content files.
