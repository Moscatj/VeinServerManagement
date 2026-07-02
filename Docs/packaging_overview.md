# Packaging Overview

This document explains how to turn the Vein Server Management Suite into a redistributable package that
ships the PySide6 GUI (`VeinManager`) as a Windows `.exe`, bundles the Python helpers into a CLI launcher
(`VeinTools.exe`), and produces a Windows installer for GitHub Releases.

---

## 1. Build the GUI executable

Prerequisites:

1. Python 3.11 or 3.12 for packaging. Python 3.13 may be unreliable with PyInstaller on this project.
2. `py -3.12 -m pip install -r requirements-packaging.txt`

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
- `Config/config.yaml` ships with relative paths (Runtime, Logs, `../VeinServer`, etc.) so the suite can be installed on any drive; update `paths.server_root` and related entries after install if your Vein server lives elsewhere.
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

1. Install packaging dependencies: `py -3.12 -m pip install -r requirements-packaging.txt`.
2. Install Inno Setup (https://jrsoftware.org/isinfo.php).
3. Run `Scripts\BuildInstaller.bat`.
4. The build script stages the PyInstaller bundle, compiles the Inno installer, and passes the latest Git tag as `MyAppVersion`.
5. Set `PYTHON_BIN` to choose the packaging runtime, for example `set "PYTHON_BIN=py -3.12"`.
6. Set `VEIN_PACKAGE_VERSION` to override the installer version for local test builds.
7. Output goes to `dist/installer/VeinServerManagement-Setup.exe`.

Installer responsibilities (current + future):

- Copy the staged folder into `C:\Program Files\VeinServerManagement`
- Create Start Menu/Desktop shortcuts (`VeinManager`, docs, log folder)
- Offer to create writable `Logs/`, `Backups/`, `Runtime/` under `%ProgramData%` in a later iteration
- Register an uninstaller entry in Add/Remove Programs
- (Future) Allow optional installation of services/shortcuts for the crash/log monitors

---

## 4. Roadmap / Next Steps

1. **Release artifact workflow** - publish `VeinServerManagement-Setup.exe` on GitHub Releases for each stable release tag.
2. **Installer smoke tests** - add CI or a local release checklist step that builds the PyInstaller bundle and validates `VeinManager.exe`, `VeinTools.exe`, and staged config files exist.
3. **Installer polish** - expose destination folders, add clearer post-install config guidance, integrate with Windows Firewall prompts, and optionally register scheduled tasks only when the operator opts in.
4. **Fresh install validation** - test the installer on a clean Windows profile or VM with no repo checkout and no local Python dependency.

---

Questions or improvements? Capture them in this doc so packaging stays reviewable.
