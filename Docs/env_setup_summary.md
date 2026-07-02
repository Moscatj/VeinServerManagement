# env_setup.bat — Summary  
**Vein Server Management Suite**

---

## Purpose
`env_setup.bat` initializes the **environment variables** required by all Windows batch
launchers and Python controllers in the Vein Server Management Suite.

Every script (`StartServer.bat`, `StartCrashMonitor.bat`, `StartLogMonitor.bat`,
`ShutdownServer.bat`, etc.) begins by calling this file to guarantee a consistent runtime environment.

---

## Core Responsibilities
1. Detect and define the **Server Management root** (`VEIN_MGMT_ROOT`).
2. Configure key environment variables used by Python and child processes.
3. Normalize all relevant folder paths (using Windows absolute syntax).
4. Display the resolved environment for transparency during debugging.
5. Exit cleanly if the expected structure is missing.

---

## Typical Variables Set

| Variable | Description |
|-----------|-------------|
| **VEIN_MGMT_ROOT** | Absolute path to the Server Management suite root. Normally the folder containing `Controller/`, `Config/`, and `Scripts/`. |
| **VEIN_MGMT_SCRIPTS** | Points to the `Scripts/` subfolder containing the batch utilities. |
| **VEIN_MGMT_CONTROLLER** | Points to `Controller/`, where all Python logic lives (`start_server.py`, `Controller/Tools/*`, etc.). |
| **VEIN_CONFIG** | Absolute path to the active local configuration file (`Config/config.yaml`). |
| **PYEXE** | Python executable command used by all scripts (`py -3`, `py -3w`, or a full path). |
| **RUNTIME_DIR** | (Optional) Path to the Runtime directory containing flags, PID, and state JSONs. |
| **PATH** | Updated so that Python and SteamCMD (if applicable) are discoverable. |

---

## Example Execution Flow
When any start/stop script is run, the following occurs:
1. `call env_setup.bat`
2. Batch logic sets environment variables and echoes them to the console:
       [env] VEIN_MGMT_ROOT=<VEIN_MGMT_ROOT>
       [env] VEIN_CONFIG=<VEIN_MGMT_ROOT>\Config\config.yaml
       [env] PYEXE=py -3
3. Control returns to the calling script (e.g., `StartServer.bat`).
4. That script then calls the relevant Python entrypoint under `Controller/`.

---

## Integration Points
| Consumer | How it Uses the Variables |
|-----------|----------------------------|
| **StartServer.bat** | Launches `Controller/start_server.py` using `%PYEXE%` and `%VEIN_CONFIG%`. |
| **StartCrashMonitor.bat** | Starts `Controller/crash_monitor.py`. |
| **StartLogMonitor.bat** | Starts `Controller/monitor_log.py`. |
| **ShutdownServer.bat** | Uses the same environment to stop the running server cleanly. |
| **Python controllers** | Read `VEIN_MGMT_ROOT` and `VEIN_CONFIG` automatically via `os.environ`. |

---

## Design Notes
- Designed for Windows CMD (not PowerShell).  
- Uses simple `set` statements—no admin privileges required.  
- Supports both interactive double-click and `cmd /c` invocation.  
- Environment variables persist **only for the lifetime** of the process (no registry writes).  
- Keep relative path references minimal; always prefer absolute drive paths.

---

## Maintenance Tips
- Update `VEIN_MGMT_ROOT` if the suite is moved to a new drive or folder.  
- If Python fails to launch, verify the `PYEXE` line matches your installed version (`py -3`, `python`, etc.).  
- If you add new submodules (e.g., WebAdmin), export new variables here so other scripts can locate them.  
- Avoid spaces in paths where possible—batch quoting rules can be brittle.

---

## Example Addition (if you extend suite)
To add a new environment variable:
set VEIN_WEBADMIN=%VEIN_MGMT_ROOT%\WebAdmin
echo [env] VEIN_WEBADMIN=%VEIN_WEBADMIN%

yaml
Copy code
Now any script can reference `%VEIN_WEBADMIN%` without hard-coding.

---

_Last updated by AI code analysis for the Vein Server Management project._
