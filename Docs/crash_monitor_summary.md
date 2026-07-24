# crash_monitor.py — Summary
**Vein Server Management Suite**

---

## Purpose
`crash_monitor.py` watches the Vein server’s **runtime state** and **process health**.  
If the server exits unexpectedly (flag says “running” but no process exists), it triggers a **controlled restart** and notifies Discord. It also exposes a small heartbeat/state JSON for the GUI and supports clean shutdown via a stop flag.

**Core responsibilities**
- Poll for server process + runtime flag alignment (running vs. not).
- Respect **intentional shutdown** and **quiet windows** (startup grace, anti-thrash).
- Attempt a **controlled restart** when a crash is detected.
- Maintain PID/state files for the **GUI**.
- Post **Discord** updates (started, idle, watching, restart, stopped).

---

## Runtime Files & Flags
- **PID:** `Runtime/crash_monitor.pid` — PID of the monitor.
- **State:** `Runtime/crash_monitor_state.json` — `{ts, mode, pid}` for GUI gumdrop.
- **Stop flag:** `Runtime/stop_crash_monitor.flag` — request a clean exit.
- **Server state flag:** `Runtime/server_running.flag` — records whether a
  managed server should be running.

**State “modes” written:**
- `startup`, `stopped`, `disabled`, `intentional_shutdown`, `idle`, `watching`, `restart_pending`

---

## Configuration (read at runtime)
- `crash_monitor_interval_seconds` → **polling interval** (min 5s; default ~300s)
- `crash_monitor_idle_notify_minutes` → **repeat idle notice** cadence (default ~15m)
- `features.enable_crash_monitor` → live enable/disable

These are read via the shared config helper; no hardcoded constants beyond safe minimums.

---

## Discord Notifications
Channel: `monitor` (routed and gate-checked by `Tools.discord`)

Typical messages:
- 🟢 Crash monitor started / active
- 🟡 Idle: server flag not present (server offline)
- 🧭 Watching for unexpected exit
- ❌ Crash detected; attempting controlled restart…
- 🔄 Auto-restart initiated
- 🛑 Stop requested; exiting

---

## Key Behaviors

### Startup & Identity
- Writes its PID to `crash_monitor.pid`.
- Emits a “started” Discord message.
- Writes `startup` state to `crash_monitor_state.json`.

### Stop Handling
- If `stop_crash_monitor.flag` exists:
  - Writes `stopped` state, cleans PID + flag, sends stop message, exits.

### Live Enable/Disable
- If `features.enable_crash_monitor` is **false**:
  - Writes `disabled` state and sleeps (does **not** exit), allowing live re-enable.

### Intentional Shutdown Suppression
- If an **intentional shutdown** is underway:
  - Writes `intentional_shutdown` state and waits; no restart attempts.

### Server State Logic
- **No server flag present** → `idle` state
  - Sends an initial idle message, then repeats every `crash_monitor_idle_notify_minutes`.
- **Flag present + server process alive** → `watching` state
  - Sends a one-time “watching” message, then sleeps.
- **Flag present + process missing** → `restart_pending` state (**crash**)
  - First checks **quiet windows**:
    - **Startup grace** (to avoid false positives right after launch)
    - **Auto-restart quiet period** (to prevent restart thrash)
  - If allowed, triggers `initiate_controlled_restart(reason="proc_missing")`.
  - Posts Discord about restart success vs. throttled/in-progress conditions.
  - Sleeps briefly (e.g., ~30s) to let the orchestrator work.

### Exit Cleanup
- On any exit path, PID/stop flag is cleaned up.
- State file is updated to reflect terminal state.

---

## Integration Points
- **Controller/Tools/** modules (process, runtime, restart)  
  - Paths: `RUNTIME_DIR`, `STATE_FLAG`  
  - Process/flags: `find_running_server()`, `is_shutdown_in_progress()`  
  - Windows/throttle logic: `startup_grace_active()`, `autorestart_quiet_active()`  
  - Restart orchestration: `initiate_controlled_restart(reason=...)`  
  - Discord: `send_discord_message(msg, channel="crash_monitor")`
- **start_server.py**  
  - Creates startup lock & grace windows that this monitor respects.
- **vein_manager.py (GUI)**  
  - Reads `crash_monitor_state.json` and `crash_monitor.pid` for status.
  - Can create `stop_crash_monitor.flag` to request a clean stop.

---

## Error & Safety Considerations
- **Atomic state writes** prevent partial JSON (write to `.tmp` then replace).
- **Quiet windows** ensure the monitor doesn’t flap during boot or crash storms.
- **Live feature gating** allows enabling/disabling without restart.
- Controlled restart requests acquire an exclusive runtime lock. A competing
  request never removes a lock it does not own, launch failures return safely
  to the monitor loop without writing a throttle stamp, and Discord failures do
  not prevent the local restart attempt.
- **No hardcoded paths** — everything flows through the config/runtime helpers.

---

## Quick Customization
| Goal | Where to change |
|------|------------------|
| Faster/slower polling | `crash_monitor_interval_seconds` |
| Idle reminder cadence | `crash_monitor_idle_notify_minutes` |
| Disable monitoring without stopping script | `features.enable_crash_monitor` |
| Adjust Discord chatter | Use Discord channel/message gates in config |
| Throttle restarts | Tune crash-monitor backoff/breaker and runtime quiet-period settings |

---

_Audited against v2.9.0 on 2026-07-14._
