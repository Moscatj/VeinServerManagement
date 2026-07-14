# Architecture Decision Records

These short records preserve settled project choices that future contributors
and AI sessions should understand before proposing a different direction.
They explain why a choice exists; current commands and behavior remain in the
operator and developer documentation.

Use the next sequential number for a durable decision that affects multiple
subsystems, packaging, compatibility, safety, or future architecture. Record:

- status (`Accepted`, `Superseded`, or `Deprecated`);
- context and constraints;
- the decision;
- important consequences and tradeoffs; and
- links to the current implementation guidance.

Do not create an ADR for routine implementation details. If a decision changes,
add a new record and mark the old record `Superseded` rather than rewriting its
history.

## Accepted Decisions

- [0001 — Package with Python 3.12](0001-package-with-python-3-12.md)
- [0002 — Derive game log and save paths](0002-derive-server-data-paths.md)
- [0003 — Delegate GUI process control](0003-delegate-gui-process-control.md)
- [0004 — Prefer app-managed SteamCMD](0004-prefer-app-managed-steamcmd.md)
- [0005 — Ship Windows first and design for Linux](0005-windows-first-linux-ready.md)
