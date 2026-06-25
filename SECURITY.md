# Security Policy

## Supported Versions

This is a personal open-source project. Security fixes are made on the current `main` branch.

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

The Vein game install is outside this repository. Management code should only read game logs/saves and should not modify game install files.
