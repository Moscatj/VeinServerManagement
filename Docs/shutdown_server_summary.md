# shutdown_server.py — Summary
**Vein Server Management Suite**

---

## Purpose
`shutdown_server.py` performs a **clean, coordinated shutdown** of the Vein dedicated server and its monitors.  
It marks the shutdown as **intentional** (so the crash monitor won’t auto-restart), stops the monitors first, then stops the server, triggers a backup, posts Discord notifications, and cleans up runtime flags/locks. If config loading fails, it falls back to an **emergency stop** path.

---

## Bootstrap & Environment
- Resolves `Controller/`, `MGMT_ROOT`, and `Config/` based on the script’s path.
- Looks up `VEIN_CONFIG` deterministically from:
  1) `os.environ["VEIN_CONFIG"]`
  2) `Config/config.yaml`
  3) `Config/config.yml`
  4) legacy JSON locations through the normal config loader
- Exports `VEIN_MGMT_ROOT` and `VEIN_CONFIG` to the environment so helpers can read them.
- Prints which config is being used for visibility in the console.

---

## Key Helpers
- **Tools.monitors:** `stop_log_monitor()`, `stop_crash_monitor()`
- **Tools.discord:** `send_discord_message(...)`
- **Tools.backups_api:** `make_backup(reason="Shutdown")`
- **Tools.runtime:** intentional-shutdown markers, server state, locks, and
  autorestart quiet periods
- **Tools.process:** process discovery and the shared aggressive stop fallback
- **config_helper:** normalized configuration and feature gates

---

## Primary Functions

### `_taskkill_by_name(name)`
Best-effort `taskkill /IM <name> /T /F` without raising.

### `_stop_py_process(keyword)`
Finds Python processes whose command line contains `keyword` and kills them (fallback if helpers fail).

### `_clear_locks()`
Deletes legacy Controller-local locks/flags:
- `startup_in_progress.lock`
- `no_autorestart.until`
- `server_running.flag`

### `_warn_and_wait(seconds)`
Optional pre-shutdown countdown:
- Posts Discord “server will shut down in X seconds…”
- Prints a 1-second decrementing countdown to console.

### `_normal_shutdown()`
Clean shutdown sequence:
1. **Mark intent & quiet window**  
   - `begin_intentional_shutdown(window_sec=…)`
   - Clear the running flag (`clear_flag()`).
2. **Stop monitors first**  
   - Assert both canonical monitor stop flags until the next startup clears them.
   - Try `stop_log_monitor()` / `stop_crash_monitor()`; on failure, kill by keyword.
   - After a confirmed stop, persist terminal monitor state and remove its stale
     PID marker so the GUI cannot display an old `active` or `idle` state.
   - This prevents GUI recovery polling from relaunching a monitor while the
     server is still alive during the shutdown warning window.
3. **Optional warning**  
   - If `pre_shutdown_warning_seconds` > 0 → run `_warn_and_wait()`.
4. **Stop the server**  
   - If no PIDs found: log + Discord “shutdown requested, but server not running.”  
   - Else: print PIDs and `stop_all_vein_processes_aggressive()`.
5. **Backup + notify**  
   - `backup_save_file(..., reason="Shutdown")` (best-effort)  
   - Discord “shutdown complete. Backup created.”
6. **Cleanup**  
   - `_clear_locks()` and `end_intentional_shutdown()`  
   - Print “Shutdown complete.”

### `_emergency_shutdown()`
Used if early config import fails.  
Kills monitors by keyword and taskkills likely server executables:
- `VeinServer-Win64-Shipping.exe`
- `VeinServer-Win64-Test.exe`
- `VeinServer-Win64-Development.exe`
- `VeinServer.exe`  
Then clears locks and prints guidance to fix `config.yaml`.

### `main()`
- Attempts `_normal_shutdown()` if config was loaded; otherwise runs `_emergency_shutdown()`.

---

## Discord Messaging
- Pre-shutdown warning (optional)
- “Shutdown requested, but server not running.” (when applicable)
- “Server shutdown complete. Backup created.” (best-effort)
> All Discord sends are best-effort and won’t break the shutdown flow if they fail.

---

## Behavior Guarantees
- **Crash-safe:** Marks **intentional shutdown** so crash monitor won’t restart the server.
- **Monitor-first stop:** Prevents misclassification of the shutdown as a crash.
- **Best-effort backup:** Creates a save backup on shutdown; failures are logged but non-fatal.
- **Cleanup:** Clears locks/flags even if some steps fail.

---

## Quick Customization
| Goal | Where |
|------|------|
| Add/adjust pre-shutdown countdown | `pre_shutdown_warning_seconds` in `config.yaml` |
| Change quiet/throttle window after shutdown | `begin_intentional_shutdown(window_sec=…)` (config-driven) |
| Add more server executable names | `_emergency_shutdown()` exe list |
| Reduce Discord chatter | Wrap or gate `send_discord_message(...)` calls |

---

## Typical Callers / Flow
- Invoked by **GUI** “Stop Server” button or **Scripts** (`ShutdownServer.bat`).
- Complements `start_server.py` (which clears intent at start).
- Leaves the system ready for a clean subsequent `start_server.py`.

---

_Audited against v2.9.0 on 2026-07-14._
