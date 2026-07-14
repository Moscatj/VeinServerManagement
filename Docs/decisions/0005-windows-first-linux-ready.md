# 0005 — Ship Windows First and Design for Linux

**Status:** Accepted

## Context

The current application, installer, process helpers, and dedicated server
workflow are Windows-oriented. Native Linux and WSL2 hosting remain valuable
goals, but claiming support before process, filesystem, service, packaging, and
network behavior are tested would be misleading.

## Decision

Ship and support Windows packages first. Keep shared logic platform-neutral
where practical and isolate Windows-specific process, installer, and path
behavior so native Linux and WSL2 support can be introduced deliberately.

## Consequences

Linux work requires its own packages, service model, CI, and clean-machine
tests. WSL2 is treated as Linux hosting with additional Windows networking and
filesystem guidance, not as a Windows virtual-machine licensing requirement.

See [linux_wsl_support.md](../linux_wsl_support.md) and
[ROADMAP.md](../../ROADMAP.md).
