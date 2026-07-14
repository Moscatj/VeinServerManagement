# env_setup.bat — Summary  
**Vein Server Management Suite**

---

## Purpose
`env_setup.bat` derives the repository paths used by the Windows source
wrappers. It is not used by packaged installations.

Every script (`StartServer.bat`, `StartCrashMonitor.bat`, `StartLogMonitor.bat`,
`ShutdownServer.bat`, etc.) begins by calling this file to guarantee a consistent runtime environment.

---

## Core Responsibilities
1. Derive `VEIN_MGMT_ROOT` from the script's own `Scripts\` location.
2. Set `VEIN_MGMT_SCRIPTS` and `VEIN_MGMT_CONTROLLER`.
3. Echo only those resolved paths for source-launch diagnostics.
4. Return control to the calling batch wrapper without changing the registry or
   the parent process's persistent environment.

---

## Typical Variables Set

| Variable | Description |
|-----------|-------------|
| **VEIN_MGMT_ROOT** | Absolute path to the Server Management suite root. Normally the folder containing `Controller/`, `Config/`, and `Scripts/`. |
| **VEIN_MGMT_SCRIPTS** | Points to the `Scripts/` subfolder containing the batch utilities. |
| **VEIN_MGMT_CONTROLLER** | Points to `Controller/`, where all Python logic lives (`start_server.py`, `Controller/Tools/*`, etc.). |

`env_setup.bat` does not currently set `VEIN_CONFIG`, `PYEXE`, `RUNTIME_DIR`,
or `PATH`. Calling wrappers select their Python command as needed, and the
Python config loader resolves the active config.

---

## Example Execution Flow
When any start/stop script is run, the following occurs:
1. `call env_setup.bat`
2. Batch logic sets repository path variables and echoes them to the console:
       [env] VEIN_MGMT_ROOT=<VEIN_MGMT_ROOT>
       [env] VEIN_MGMT_SCRIPTS=<VEIN_MGMT_ROOT>\Scripts
       [env] VEIN_MGMT_CONTROLLER=<VEIN_MGMT_ROOT>\Controller
3. Control returns to the calling script (e.g., `StartServer.bat`).
4. That script then calls the relevant Python entrypoint under `Controller/`.

---

## Integration Points
| Consumer | How it Uses the Variables |
|-----------|----------------------------|
| **StartServer.bat** | Launches `Controller/start_server.py` after resolving the repository root. |
| **StartCrashMonitor.bat** | Starts `Controller/crash_monitor.py`. |
| **StartLogMonitor.bat** | Starts `Controller/monitor_log.py`. |
| **ShutdownServer.bat** | Uses the same environment to stop the running server cleanly. |
| **Python controllers** | May read `VEIN_MGMT_ROOT`; config selection is handled by `config.py`. |

---

## Design Notes
- Designed for Windows CMD (not PowerShell).  
- Uses simple `set` statements—no admin privileges required.  
- Supports both interactive double-click and `cmd /c` invocation.  
- Environment variables persist **only for the lifetime** of the process (no registry writes).  
- Keep relative path references minimal; always prefer absolute drive paths.

---

## Maintenance Tips
- Do not hardcode `VEIN_MGMT_ROOT`; moving the repo is supported because it is derived.
- If Python fails to launch, inspect the calling wrapper's Python selection.
- If you add new submodules (e.g., WebAdmin), export new variables here so other scripts can locate them.  
- Avoid spaces in paths where possible—batch quoting rules can be brittle.

---

## Extending The Wrapper Environment

Add variables only when multiple source wrappers truly need them. Keep values
derived from `VEIN_MGMT_ROOT`, quote assignments, and do not persist them to the
system environment or registry.

---

_Audited against v2.9.0 on 2026-07-14._
