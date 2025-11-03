# monitor_log.py — Summary
**Vein Server Management Suite**

---

## Purpose
`monitor_log.py` tails the active Vein server log and turns lines into **live state** and **Discord events**.  
It detects server readiness, player activity, autosaves, and crash signatures, writes a lightweight
state file for the GUI, and exits cleanly when the server stops or a stop flag is set.

**Core responsibilities**
- Pick the active Vein log file (from `Config` absolute path or newest `Vein*.log`).
- Tail and parse lines for server/players/autosaves/crash patterns.
- Write heartbeat/state for the GUI (`Runtime/log_monitor_state.json`, `log_monitor.pid`).
- Respect feature flags for **what** to track and **what** to notify on Discord.

---

## Key Files & Paths
- **PID:** `Runtime/log_monitor.pid` — PID of the running log monitor (GUI uses this).
- **State:** `Runtime/log_monitor_state.json` — `{last_updated, active, tailing_file, watching_server}`.
- **Stop flag:** `Runtime/stop_log_monitor.flag` — if present, monitor stops gracefully.
- **Log dir:** from `utils.LOGS_DIR`; optional `utils.ABSOLUTE_LOG_FILE` overrides selection.

---

## Configuration (with defaults)
All pulled from `config.get("monitor", {})` with sensible fallbacks.

- **Intervals & polling**
  - `state_refresh_seconds` → default **15** (refresh GUI state, independent of Discord)
  - `monitor_heartbeat_interval_seconds` → default **300** (Discord heartbeat if enabled)
  - `wait_for_log_appearance_seconds` → default **120** (grace window for log to appear)
  - `tail_poll_interval_ms` → default **500** (tail loop sleep when idle)

- **Tracking toggles** (what to parse from the log)
  - `track.startup` (default **true**)
  - `track.auth` (default **true**)
  - `track.join` (default **true**)
  - `track.character` (default **true**)
  - `track.disconnect` (default **true**)
  - `track.autosave` (default **true**)
  - `track.crash` (default **true**)
  - `track.heartbeat` (default **true**)

- **Notification toggles** (what to send to Discord)
  - `notify.startup` (default **true**)
  - `notify.joinable` (default **true**)
  - `notify.auth` (default **true**)
  - `notify.join` (default **true**)
  - `notify.character` (default **true**)
  - `notify.disconnect` (default **true**)
  - `notify.autosave` (default **false**)
  - `notify.crash` (default **true**)
  - `notify.heartbeat` (default **false**)
  - `notify.monitor_status` (default **true**)

- **Backups on autosave**
  - `monitor.backups.on_autosave` (default **true**)
  - `autosave_backup_cooldown_seconds` (default **300**)

> Notifications also require per-channel enablement via `utils.is_discord_channel_enabled(channel)`.

---

## Regex Patterns (log signatures)
- **Server joinable:**  
  `RamjetSteamNetDriver_* started listening on (\d+)`  
  `LogWorld: Bringing World .* up for play`  
  `Steamworks server initialized`
- **Auth/Login:** `LogRamjetNetworking: Authenticated (\d+)`
- **Join:** `LogNet: Join succeeded:\s*(.+)`
- **Character select:** `selected character .* (aka ([^)]+))`
- **Disconnect:** `closed by peer|Logout|Connection closed`
- **Autosave:** `LogVeinSaveGame: Saved save game to disk`
- **Crash:** `Fatal error|Access violation|EXCEPTION_ACCESS_VIOLATION|Assertion failed|ensure\(!\)`

---

## Important Functions

### `monitor()`
Main loop:
1. Write PID → `Runtime/log_monitor.pid`.
2. Emit “starting…” Discord (if `notify.monitor_status`).
3. Wait up to `wait_for_log_appearance_seconds` for a log file:
   - Prefer `ABSOLUTE_LOG_FILE` if exists; else newest `Vein*.log` in `LOGS_DIR`.
   - If `stop_log_monitor.flag` appears, exit cleanly.
   - If timeout, warn (Discord) and exit.
4. Mark **active** in `log_monitor_state.json` and announce active (Discord).
5. Tail the file:
   - If server is no longer running → write inactive state, announce stop, exit.
   - Every `state_refresh_seconds` → refresh state JSON for GUI.
   - On **ready/joinable** signature → send “Server is up and joinable.”
   - On **auth** → “Auth OK for `<steam_id>`.”
   - On **join** → “`<name>` joined.” (track in a `current_players` set)
   - On **character select** → “`<name>` selected a character.”
   - On **disconnect** → “A player disconnected.”
   - On **autosave** → (debounced by `autosave_backup_cooldown_seconds`)
     - If `monitor.backups.on_autosave` → `utils.backup_save_file(reason="AutoSave")`
     - Optional Discord: “Autosave detected — backup created.”
   - On **crash signature** → Discord alert: “Crash signature in log! Check server.”
   - On **heartbeat interval** (if enabled) → refresh state + optional Discord heartbeat.
6. Always on exit (finally) → mark inactive, remove PID file.

### `_write_logmon_state(active, tailing_file=None, watching_server=None)`
Atomic JSON write (`.tmp` + replace) with UTC timestamp. Consumed by GUI for green/yellow/red gumdrop state.

### `_pick_log_file()`
Chooses the log source: `config.absolute_log_file` first, else newest `Vein*.log` in `LOGS_DIR`.

### `_discord(msg, channel="monitor")`
Sends a message to Discord only if that channel is enabled.

### `tail_log(fp)`
Generator that yields new lines as they’re written; sleeps `tail_poll_interval_ms` when idle.

---

## Discord Channels Used
- `monitor` — status, joinable, auth/join/character/disconnect, autosave, crash alerts, heartbeats (if enabled)

---

## Integration Points
- **GUI (vein_manager.py):**
  - Reads `log_monitor_state.json` and `log_monitor.pid` to show live status.
  - Can create `stop_log_monitor.flag` to request a clean shutdown.
- **utils.py:**
  - `is_server_running()` to stop monitoring when server ends.
  - `send_discord_message()` for all outbound notifications.
  - `backup_save_file()` for autosave-triggered backups.
- **start_server.py:**
  - Spawns this monitor (idempotently) post-boot, depending on feature flags.

---

## Exit Conditions
- `stop_log_monitor.flag` file appears.
- Server process is no longer running.
- Log file never appears within the configured wait window.
- Any unhandled exception (state and PID are still cleaned up in `finally`).

---

## Error/Safety Considerations
- All state writes are **atomic** to avoid partial JSON reads in the GUI.
- Monitor exits on server stop to avoid stale status.
- Backups during autosave are **debounced** to avoid thrash.
- Regexes are case-insensitive where appropriate (`re.I`).
- Notifications respect both **track** and **notify** flags.

---

## Quick Customization
| Goal | Knob / Area |
|------|--------------|
| Shorten/lengthen GUI refresh | `state_refresh_seconds` |
| Faster/slower tail loop | `tail_poll_interval_ms` |
| Control autosave backup frequency | `autosave_backup_cooldown_seconds` |
| Turn on/off Discord categories | `monitor.notify.*` toggles |
| Disable entire behavior (e.g., crash alerts) | `monitor.track.*` toggles |
| Change monitored log source | `config.absolute_log_file` / `LOGS_DIR` |

---

_Last updated by AI code analysis for the Vein Server Management project._
