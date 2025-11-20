# Packaging Overview

This document explains how to turn the Vein Server Management Suite into a redistributable package that
ships the PySide6 GUI (`VeinManager`) as a Windows `.exe`, bundles the Python helpers, and prepares for a
full installer.

---

## 1. Build the GUI executable

Prerequisites:

1. Python 3.11+
2. `pip install pyinstaller`

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

> ⚠️ **Sensitive config**: the staging step copies whichever files currently live under `Config/`.
> Sanitize webhooks/passwords before distributing a build.

---

## 2. Expected release layout

```
VeinServerManager/
?"o?"? VeinTools.exe                  # Console CLI for headless helpers
├─ VeinManager.exe                # GUI launcher
├─ Controller/                    # Python automation scripts + Tools/ helpers
├─ Config/                        # YAML config templates (edit in-place after install)
├─ Scripts/                       # Batch helpers for CLI workflows
├─ Docs/                          # Reference docs
├─ Backups/ (empty placeholder)   # Created on first run
├─ Logs/ (empty placeholder)
└─ Runtime/ (empty placeholder)
```

This mirrors the repository structure so that the GUI can keep resolving `Controller/*`
helpers and runtime directories without additional configuration.

---

## 3. Installer plan (Inno Setup)

An initial Inno Setup script lives at `Installer/VeinServerManager.iss`. Run it after
staging the bundle to produce `VeinServerManager-Setup.exe`.

Workflow:

1. Build/stage the bundle (`py -3 Controller\Tools\packing\build_gui_exe.py`)  
   *(Shortcut: run `Scripts\BuildInstaller.bat` to run this step and the Inno compiler in one go.)*
2. Install Inno Setup (https://jrsoftware.org/isinfo.php)
3. Open `Installer/VeinServerManager.iss`
4. Update the `#define MyAppVersion` to match the release
5. Compile → output goes to `dist/installer/`

Installer responsibilities (current + future):

- Copy the staged folder into `C:\Program Files\VeinServerManagement`
- Create Start Menu/Desktop shortcuts (`VeinManager`, docs, log folder)
- Offer to create writable `Logs/`, `Backups/`, `Runtime/` under `%ProgramData%` in a later iteration
- Register an uninstaller entry in “Add/Remove Programs”
- (Future) Allow optional installation of services/shortcuts for the crash/log monitors

---

## 4. Roadmap / Next Steps

1. **Automated config templating** – add a sanitized `Config/config.example.yaml` and teach the builder
   to copy/rename it by default so secrets never leak.
2. **Optional monitor executables** – re-use PyInstaller to ship `start_server.py`,
   `monitor_log.py`, etc., as CLI tools for hosts that do not install Python.
3. **Installer polish** – expose destination folders, integrate with Windows Firewall prompts,
   and optionally register scheduled tasks (nightly backups) if the operator opts in.
4. **Smoke tests** – add a basic CI workflow that runs the builder with `--skip-stage`
   to ensure PyInstaller stays happy as dependencies evolve.

---

Questions or improvements? Capture them in this doc so packaging stays reviewable.
