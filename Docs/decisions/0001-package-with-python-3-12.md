# 0001 — Package with Python 3.12

**Status:** Accepted

## Context

Packaged users must not need Python. Development supports Python 3.11 and 3.12,
while Python 3.13 has historically introduced avoidable PyInstaller and native
dependency uncertainty for this project.

## Decision

Build Windows executables and installers with Python 3.12. CI runs unit tests on
3.11 and 3.12, with full validation, coverage, and packaging on 3.12. Python
3.13 remains experimental until the packaging stack is deliberately qualified.

## Consequences

Packaging is reproducible and aligned with the maintainer environment. Supporting
a newer runtime requires an explicit CI and clean-installer validation change,
not merely a documentation edit.

See [packaging_overview.md](../packaging_overview.md) and
[testing.md](../testing.md).
