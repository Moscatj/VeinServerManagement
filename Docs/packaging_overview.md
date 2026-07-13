# Packaging Overview

This document explains how to turn the Vein Server Management Suite into a redistributable package that
ships the PySide6 GUI (`VeinManager`) as a Windows `.exe`, bundles the Python helpers into a CLI launcher
(`VeinTools.exe`), and produces a Windows installer for GitHub Releases.

---

## 1. Build the GUI executable

Prerequisites:

1. Python 3.11 or 3.12 for packaging. Python 3.13 may be unreliable with PyInstaller on this project.
2. `py -3.12 -m pip install -r requirements-dev.txt -r requirements-packaging.txt`

Command:

```powershell
py -3 Controller\Tools\packing\build_gui_exe.py
```

What happens:

- PyInstaller compiles `Controller/vein_manager.py` into `dist/VeinManager/VeinManager.exe`
  (use `--onefile` for a single binary if desired).
- The script stages a self-contained bundle in `dist/VeinServerManager/` containing:
  - `VeinManager.exe` + PyInstaller support files
  - `Controller/`, `Config/`, `Scripts/`, and `Docs/`
  - empty `Backups/`, `Logs/`, and `Runtime/` directories
  - README/AGENTS/docs_for_codex for reference
- `Config/config.yaml` is staged from the public app-managed template. During install, the installer asks for the Vein dedicated server root and optional SteamCMD path, then rewrites the installed runtime config paths to match those choices. SaveGames and the Vein Game Log are derived automatically from the server root. SteamCMD installs default to the app-managed `Server\` folder.
- During staging the builder copies `Config/config.example.yaml` into the bundle as `Config/config.yaml`, ensuring secrets from your live config never leak. Customize the installed copy after deployment.

- A console-friendly launcher (`VeinTools.exe`) is built alongside the GUI so you can trigger helper scripts without installing Python.

### CLI launchers

The packaged CLI lives next to the GUI and mirrors the common BAT entrypoints:

```powershell
.\VeinTools.exe start-server          # launch the Vein dedicated server
.\VeinTools.exe stop-server           # clean shutdown (same as shutdown_server.py)
.\VeinTools.exe restart-server        # stop + start with a short delay
.\VeinTools.exe monitor-log           # run log monitor (blocking)
.\VeinTools.exe stop-log-monitor      # request log monitor shutdown
.\VeinTools.exe crash-monitor         # run crash monitor (blocking)
.\VeinTools.exe stop-crash-monitor    # stop the crash monitor
.\VeinTools.exe stop-all-monitors     # stop both monitors
.\VeinTools.exe nightly-backup        # run the nightly backup routine immediately
.\VeinTools.exe health-check          # validate config, paths, SteamCMD, and server executable
```

Add `--config <path>` if you need to point at a non-default configuration file; the default is `Config/config.yaml` under the install root.

Flags:

- `--onefile`: produce a single-file EXE (default is onedir for faster startup and easier patching)
- `--skip-stage`: leave the PyInstaller output alone (useful for debugging)
- `--skip-cli`: skip building VeinTools.exe (useful for GUI-only debugging)
- `--dist`, `--build`, `--bundle`: override output directories

> Sensitive config: the staging step ignores local `Config/config.yaml` and creates the packaged runtime
> config from `Config/config.example.yaml`. Keep public defaults in the example file and keep local secrets
> in ignored config or environment variables.

---

## 2. Expected release layout

```text
VeinServerManager/
|-- VeinTools.exe                 # Console CLI for headless helpers
|-- VeinManager.exe               # GUI launcher
|-- Controller/                   # Python automation scripts + Tools/ helpers
|-- Config/                       # YAML config templates and runtime config
|-- Scripts/                      # Batch helpers for CLI workflows
|-- Docs/                         # Reference docs
|-- Backups/                      # Empty placeholder; created on first run
|-- Logs/                         # Empty placeholder
|-- SteamCMD/                     # App-managed SteamCMD when selected
|-- Server/                       # App-managed Vein dedicated server root
`-- Runtime/                      # Empty placeholder
```

This mirrors the repository structure so that the GUI can keep resolving `Controller/*`
helpers and runtime directories without additional configuration.

---

## 3. Installer plan (Inno Setup)

An initial Inno Setup script lives at `Installer/VeinServerManager.iss`. Run it after
staging the bundle to produce a versioned installer executable.

Workflow:

1. Install app and packaging dependencies: `py -3.12 -m pip install -r requirements-dev.txt -r requirements-packaging.txt`.
2. Install Inno Setup (https://jrsoftware.org/isinfo.php).
3. Run `Scripts\BuildInstaller.bat`.
4. The build script stages the PyInstaller bundle, compiles the Inno installer, and passes the latest Git tag as `MyAppVersion`.
5. Set `PYTHON_BIN` to choose the packaging runtime, for example `set "PYTHON_BIN=py -3.12"`.
6. Set `VEIN_PACKAGE_VERSION` to override the installer version for local test builds.
7. Output goes to `dist/installer/VeinServerManagement-Setup-vX.Y.Z.exe`.

GitHub release workflow:

- `.github/workflows/release-installer.yml` runs on `vMAJOR.MINOR.PATCH` tags.
- The workflow builds the PyInstaller bundle, compiles the Inno Setup installer,
  extracts release notes from the matching `CHANGELOG.md` version section,
  uploads the installer as an Actions artifact, and attaches
  a versioned installer such as `VeinServerManagement-Setup-v2.3.12.exe` to the GitHub Release.
- Manual `workflow_dispatch` runs build a temporary Actions artifact without
  publishing a release asset.

Installer responsibilities:

- Copy the staged folder into `C:\Program Files\VeinServerManagement`
- Create Start Menu/Desktop shortcuts (`VeinManager`, docs, log folder)
- Create writable app-owned `Config\`, `Logs\`, `Backups\`, `Runtime\`, `SteamCMD\`, and `Server\` folders
- Ask whether to install/update the dedicated server with SteamCMD or use an existing server folder
- Store SteamCMD in the management app folder and install new SteamCMD-managed server files under the app-managed `Server\` folder by default
- Allow an existing `steamcmd.exe` folder to be selected instead of downloading a duplicate app-managed SteamCMD copy
- Derive SaveGames and the Vein Game Log from the selected server root; custom locations are available through Quick Start's advanced overrides
- Write the installed `Config\config.yaml` paths from the selected server root so first launch points at the app-managed `Server\Vein\...` layout or the chosen external server
- Validate that the selected server root is the parent folder that contains `Vein\Binaries\Win64`, not the inner `Vein` folder itself
- Detect an existing installation with the same AppId and run as an in-place
  management-app upgrade or repair. App binaries and bundled documentation are
  refreshed while the installed `Config\config.yaml`, backups, runtime state,
  and server data are preserved.
- Present an intent page immediately after Welcome. Existing installs default to
  `Update or repair the existing installation`; operators can instead choose to
  update the management app and install a new server under a different root.
  Fresh installs explicitly choose between installing a new server and
  connecting to an existing server.
- Keep the remaining wizard goal-specific. App-only repair skips the app-folder,
  server-root, and SteamCMD pages and leaves the recorded server configuration
  untouched. New-server setup rejects the currently managed server root and
  any folder that already contains a Vein server, and defaults to the first
  available `Server-New\`, `Server-New-2\`, and so on.
- Preload the previously recorded server root and configured SteamCMD location.
  Updating the management app does not update the Vein server by default.
- Offer an explicit `Install, update, or repair` server option. When selected,
  Setup uses the canonical controlled shutdown pipeline, then runs SteamCMD
  `app_update 2131400 ... validate`. A shutdown failure skips SteamCMD rather
  than updating files beneath a running server.
- Register an uninstaller entry in Add/Remove Programs and keep Inno Setup's generated uninstaller files under `Uninstall\`
- Run a best-effort uninstall cleanup that stops log/crash monitors first and then performs a controlled server shutdown only when a Vein server process is running
- Preserve external Vein dedicated server installs by default. If the recorded server root is inside the app install folder, the uninstaller offers an explicit opt-in deletion prompt with save-loss warnings and defaults to preserving data.
- (Future) Allow optional installation of services/shortcuts for the crash/log monitors

Recommended folder layout:

```text
C:\Program Files\VeinServerManagement\
|-- VeinManager.exe
|-- VeinTools.exe
|-- SteamCMD\
|   `-- steamcmd.exe
`-- Server\
    `-- Vein\
        `-- Binaries\
            `-- Win64\
                `-- VeinServer.exe

D:\VeinServer\        # Optional external server root selected by the user
`-- Vein\
    `-- Binaries\
        `-- Win64\
            `-- VeinServer.exe

C:\steamcmd\          # Optional existing SteamCMD folder selected by the user
`-- steamcmd.exe
```

SteamCMD note:

- SteamCMD is portable; there is no single required Windows install location.
- For packaged installs, the recommended default is app-managed SteamCMD under `C:\Program Files\VeinServerManagement\SteamCMD` because it is predictable and self-contained.
- Users who already maintain SteamCMD elsewhere can select that folder to avoid duplicate downloads.
- The selected SteamCMD path is used for server install/update commands; it is separate from the dedicated server root and save/log locations.

Fresh install check:

- For a full-package install, the expected active paths are `SteamCMD\steamcmd.exe`, `Server\Vein\Binaries\Win64\...`, `Server\Vein\Saved\SaveGames`, and `Server\Vein\Saved\Logs` under the app install folder.
- The expected launch target is
  `Server\Vein\Binaries\Win64\VeinServer-Win64-Test.exe`. The smaller adjacent
  `VeinServer.exe` remains a recognized installation indicator and legacy
  fallback, but is not preferred as the dedicated runtime.
- For an existing-server install, the data paths are derived from the selected external server root.
- Run `VeinTools.exe health-check` after install to verify the config loads, writable app folders are available, SteamCMD exists when configured, and at least one configured server executable is present.
- Live logging requires no system Python installation. Bundled `VeinTools.exe`
  runs the monitor and follows `Server\Vein\Saved\Logs\Vein.log` by default.
  The GUI can enable Live before that file exists and attaches automatically
  after first startup. The Home Log Monitor card reports the selected path or
  read error, while diagnostics are captured below
  `Logs\monitors\log_monitor\`.
- If the SteamCMD app installation fails, the installer shows the management
  and SteamCMD log locations and offers Retry immediately. Cancel finishes the
  management-app installation without claiming that server files are ready;
  the GUI then directs the operator to Quick Start.

Uninstall behavior:

- The uninstaller stops management monitors and shuts down a running Vein server before removing app files.
- App-owned transient folders such as `Logs\`, `Runtime\`, and app-managed `SteamCMD\` are removed during uninstall.
- The uninstaller prompts before deleting local `Backups\` and `Config\` folders, then attempts to remove the now-empty app install folder.
- Server roots outside the app folder, such as `D:\VeinServer` or `<external drive>\Servers\VeinServer`, are preserved.
- Server roots inside the app folder can be deleted only after an explicit warning prompt. The default answer preserves saves and server data.
- External SteamCMD folders and external server data are not deleted by app-owned cleanup rules.

---

## 4. Roadmap / Next Steps

1. **Code signing** - eventually sign `VeinManager.exe`, `VeinTools.exe`, and the final installer, then verify signatures and publish checksums with releases.
2. **Installer smoke tests** - add CI or a local release checklist step that builds the PyInstaller bundle and validates `VeinManager.exe`, `VeinTools.exe`, and staged config files exist.
3. **Installer polish** - add clearer post-install config guidance, integrate with Windows Firewall prompts, and optionally register scheduled tasks only when the operator opts in.
4. **Fresh install validation** - test the installer on a clean Windows profile or VM with no repo checkout and no local Python dependency.
5. **Native Linux and WSL2 packaging** - after the backend is platform-neutral,
   publish versioned x86-64 `.deb` and `.tar.gz` assets with checksums from the
   same tags that build the Windows installer. The Linux first-run installer
   should optionally install/reuse SteamCMD, download VEIN app `2131400`, run
   health checks, and install reviewed `systemd` services. VEIN binaries must
   never be bundled. See [linux_wsl_support.md](linux_wsl_support.md).

---

Questions or improvements? Capture them in this doc so packaging stays reviewable.
