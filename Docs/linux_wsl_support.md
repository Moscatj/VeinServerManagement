# Native Linux and WSL2 Support Direction

## Goal

Support both native Linux servers and deployments where a Windows 11 desktop
hosts an Ubuntu WSL2 distribution. In either case, the VEIN Linux dedicated
server and Vein Server Management Suite run inside Linux.

This is intended to separate day-to-day Windows applications from server
processes and server data without requiring a second physical computer or a
full Windows guest virtual machine.

WSL2 is optional. An operator with a normal Ubuntu/Debian server should be able
to download a release asset from GitHub, install the management suite, and use
the guided installer to install SteamCMD and VEIN Dedicated Server without any
Windows machine.

## Current Status

The management suite is currently Windows-only. PySide6, YAML configuration,
`pathlib` paths, monitoring logic, backups, and much of Quick Start are portable,
but process control, scripts, executable discovery, configuration paths, and
packaging contain Windows-specific assumptions.

Current Steam metadata lists a Linux depot for VEIN Dedicated Server app
`2131400`, but Linux support must be validated with an actual installation
before executable names or config paths become public defaults:

- https://steamdb.info/app/2131400/depots/

## WSL2 Licensing Distinction

WSL2 runs a Linux distribution as a Windows feature. It does not install a
second copy of Windows and is not a separately licensed Windows guest virtual
machine. The Windows host must still be properly licensed, and the selected
Linux distribution, VEIN, Steam, and management-suite licenses still apply.

Running a full Windows guest in Hyper-V or another virtual-machine product is a
different scenario and may require Windows virtualization rights or an
additional license. Licensing can vary by Windows edition and use case, so this
project documentation is operational guidance rather than legal advice.

Microsoft references:

- https://learn.microsoft.com/windows/wsl/about
- https://learn.microsoft.com/windows/wsl/install

## Proposed WSL2 Layout

```text
Windows 11 host
`-- WSL2 Ubuntu
    |-- /opt/vein-management/     management application
    |-- /opt/steamcmd/            Linux SteamCMD
    |-- /srv/vein/server/         VEIN Linux dedicated server
    |-- /srv/vein/backups/        backup destination
    `-- /var/lib/vein-management/ runtime state and logs
```

Exact locations should remain configurable. Server files, saves, logs, and
runtime state should normally remain in the WSL Linux filesystem rather than
under `/mnt/c`, both for isolation and predictable Linux filesystem behavior.

## Native Linux Distribution

Each tagged release should publish these assets alongside the Windows
installer:

```text
VeinServerManagement-vX.Y.Z-linux-x86_64.deb
VeinServerManagement-vX.Y.Z-linux-x86_64.tar.gz
SHA256SUMS
```

The `.deb` is the primary Ubuntu/Debian installer. The portable archive supports
operators who cannot or do not want to install a system package. A future
AppImage may be added for GUI-only desktop convenience, but it should not replace
the CLI and `systemd` integration needed by headless hosts.

The installer/first-run experience should:

1. Install `VeinManager`, a Linux CLI command, documentation, and sanitized
   configuration defaults.
2. Create a dedicated service account and writable app-owned data directories
   when system-wide installation is selected.
3. Offer to install or reuse Linux SteamCMD.
4. Ask for the server root, branch, ports, save/log paths, and service behavior.
5. Run SteamCMD app `2131400` installation only after explicit confirmation.
6. Detect the resulting Linux executable and config layout rather than assuming
   Windows paths.
7. Run health checks before enabling or starting services.
8. Offer reviewed `systemd` units for the server and monitors.

The management package must not contain VEIN binaries. SteamCMD downloads them
from Steam under the operator's applicable Steam/VEIN terms.

## Networking

The server must be reachable by Windows-host clients and, when desired, other
machines on the LAN. The first supported target should be Windows 11 22H2 or
newer with WSL mirrored networking.

Implementation and documentation must cover:

- game, Steam query, HTTP API, and future management API ports;
- Windows and Hyper-V firewall rules;
- binding the server to an appropriate Linux interface;
- NAT-mode fallback guidance when mirrored networking is unavailable;
- confirmation from another LAN device, not only localhost testing;
- keeping unauthenticated management or game HTTP APIs off public interfaces.

Microsoft networking reference:

- https://learn.microsoft.com/windows/wsl/networking

## Service Lifecycle

Linux process management should use signals and process groups rather than
Windows `taskkill` behavior. WSL2 deployments should use reviewed `systemd`
units for the game server and monitors, including clean stop timeouts and the
existing intentional-shutdown and backup safeguards.

Microsoft documents `systemd` support in WSL here:

- https://learn.microsoft.com/windows/wsl/systemd

Windows startup integration is still required so the chosen WSL distribution
and its enabled services start after a host reboot. This must be tested rather
than assuming an interactive WSL terminal remains open.

## Implementation Phases

1. Platform-neutral backend
   - Add a small platform abstraction for process, service, file-open, and
     executable-discovery behavior.
   - Preserve existing Windows behavior and tests.
2. Linux source support
   - Run the CLI, monitors, backups, health checks, and server lifecycle from a
     Python environment on Ubuntu.
   - Validate the Linux VEIN executable and config layout.
3. WSL2 deployment support
   - Add Linux SteamCMD installation/update, WSL-aware Quick Start, `systemd`
     templates, firewall guidance, and reboot persistence testing.
4. Native Linux installer and packaging
   - Build versioned `.deb` and `.tar.gz` assets in Ubuntu CI.
   - Publish them to the matching GitHub Release with SHA256 checksums.
   - Test management installation, SteamCMD setup, VEIN download, health checks,
     service enablement, upgrades, and data-preserving uninstall on a clean VM.
5. Linux GUI
   - Validate PySide6 through WSLg.
   - Validate native Linux desktops while keeping GUI dependencies optional on
     headless hosts.
6. Optional split frontend/backend
   - Consider an authenticated local management API so a native Windows GUI can
     manage the backend running inside WSL2.

## Acceptance Criteria

- A clean Ubuntu WSL2 distribution can install SteamCMD and the VEIN Linux
  dedicated server without Windows executables.
- A clean native Ubuntu/Debian machine can install a package from GitHub and
  complete the same guided SteamCMD/VEIN setup without WSL.
- Tagged GitHub Releases contain tested Windows and Linux installers, portable
  Linux assets, and published checksums.
- Quick Start detects Linux paths and never writes Windows config locations.
- Start, graceful stop, crash recovery, log monitoring, backups, Discord
  notifications, and guarded config edits work inside Linux.
- A Windows VEIN client and a second LAN device can reach the server through
  documented firewall/network configuration.
- Services recover correctly after both a WSL shutdown and a Windows reboot.
- Windows and Ubuntu CI suites pass without weakening current safety rules.
- Windows releases remain fully supported while Linux support is introduced.
