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
- `Config/config.yaml` is staged from the public template. During install, the installer asks for the Vein dedicated server root and rewrites the installed runtime config paths to match that folder.
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
`-- Runtime/                      # Empty placeholder
```

This mirrors the repository structure so that the GUI can keep resolving `Controller/*`
helpers and runtime directories without additional configuration.

---

## 3. Installer plan (Inno Setup)

An initial Inno Setup script lives at `Installer/VeinServerManager.iss`. Run it after
staging the bundle to produce `VeinServerManager-Setup.exe`.

Workflow:

1. Install app and packaging dependencies: `py -3.12 -m pip install -r requirements-dev.txt -r requirements-packaging.txt`.
2. Install Inno Setup (https://jrsoftware.org/isinfo.php).
3. Run `Scripts\BuildInstaller.bat`.
4. The build script stages the PyInstaller bundle, compiles the Inno installer, and passes the latest Git tag as `MyAppVersion`.
5. Set `PYTHON_BIN` to choose the packaging runtime, for example `set "PYTHON_BIN=py -3.12"`.
6. Set `VEIN_PACKAGE_VERSION` to override the installer version for local test builds.
7. Output goes to `dist/installer/VeinServerManagement-Setup.exe`.

GitHub release workflow:

- `.github/workflows/release-installer.yml` runs on `vMAJOR.MINOR.PATCH` tags.
- The workflow builds the PyInstaller bundle, compiles the Inno Setup installer,
  uploads the installer as an Actions artifact, and attaches
  `VeinServerManagement-Setup.exe` to the GitHub Release.
- Manual `workflow_dispatch` runs build a temporary Actions artifact without
  publishing a release asset.

Installer responsibilities:

- Copy the staged folder into `C:\Program Files\VeinServerManagement`
- Create Start Menu/Desktop shortcuts (`VeinManager`, docs, log folder)
- Create writable app-owned `Config\`, `Logs\`, `Backups\`, and `Runtime\` folders
- Ask whether to install/update the dedicated server with SteamCMD or use an existing server folder
- Store SteamCMD in the management app folder, separate from the dedicated server install folder
- Write the installed `Config\config.yaml` paths from the selected server root so first launch does not point at `C:\Program Files\Vein`
- Validate that the selected server root is the parent folder that contains `Vein\Binaries\Win64`, not the inner `Vein` folder itself
- Register an uninstaller entry in Add/Remove Programs and keep Inno Setup's generated uninstaller files under `Uninstall\`
- Run a best-effort uninstall cleanup that stops log/crash monitors first and then performs a controlled server shutdown only when a Vein server process is running
- Preserve external Vein dedicated server installs by default. If the recorded server root is inside the app install folder, the uninstaller offers an explicit opt-in deletion prompt with save-loss warnings and defaults to preserving data.
- (Future) Allow optional installation of services/shortcuts for the crash/log monitors

Recommended folder layout:

```text
C:\Program Files\VeinServerManagement\
|-- VeinManager.exe
|-- VeinTools.exe
`-- SteamCMD\
    `-- steamcmd.exe

D:\VeinServer\
`-- Vein\
    `-- Binaries\
        `-- Win64\
            `-- VeinServer.exe
```

Uninstall behavior:

- The uninstaller stops management monitors and shuts down a running Vein server before removing app files.
- Server roots outside the app folder, such as `D:\VeinServer` or `<external drive>\Servers\VeinServer`, are preserved.
- Server roots inside the app folder can be deleted only after an explicit warning prompt. The default answer preserves saves and server data.

---

## 4. Roadmap / Next Steps

1. **Release artifact workflow** - publish `VeinServerManagement-Setup.exe` on GitHub Releases for each stable release tag.
2. **Installer smoke tests** - add CI or a local release checklist step that builds the PyInstaller bundle and validates `VeinManager.exe`, `VeinTools.exe`, and staged config files exist.
3. **Installer polish** - add clearer post-install config guidance, integrate with Windows Firewall prompts, and optionally register scheduled tasks only when the operator opts in.
4. **Fresh install validation** - test the installer on a clean Windows profile or VM with no repo checkout and no local Python dependency.

---

Questions or improvements? Capture them in this doc so packaging stays reviewable.
