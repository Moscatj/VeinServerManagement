# monitor_log.py — Summary
**Vein Server Management Suite**

---

## Purpose
`monitor_log.py` tails the active Vein server log and turns lines into **live state** and **Discord events**.  
It detects server readiness, player activity, autosaves, and crash signatures, writes a lightweight
state file for the GUI, idles lightly while the server is offline, and exits
cleanly when a stop flag is set.

**Core responsibilities**
- Pick the active Vein log file from the explicit path, configured log folder,
  or conventional app-managed server folders.
- Tail and parse lines for server/players/autosaves/crash patterns.
- Write heartbeat/state for the GUI (`Runtime/log_monitor.state.json` plus
  `log_monitor.pid`; the GUI can still read the legacy state filename).
- When `track.http_api` is enabled, poll the Vein HTTP API (status/players/time/weather), log failures to `Logs/monitors/http_api/http_api.log`, and publish structured payloads so the GUI can display world info without hammering the API.
- Maintain a rolling player cache/timeline (log + HTTP) and surface it through `Runtime/player_characters.json` plus a compact `players` block inside `log_monitor.state.json`.
- Respect feature flags for **what** to track and **what** to notify on Discord.

---

## Key Files & Paths
- **PID:** `Runtime/log_monitor.pid` — PID of the running log monitor (GUI uses this).
- **State:** `Runtime/log_monitor.state.json` — includes `last_updated`,
  `active`, `tailing_file`, `watching_server`, `status`, `message`,
  `last_line_at`, `bytes_read`, and the paths checked during discovery, plus an
  optional `http_api` payload when HTTP polling is enabled.
- **Stop flag:** `Runtime/stop_log_monitor.flag` — if present, the monitor stops
  gracefully. This is the same flag used by the GUI and packaged helper.
- **Log paths:** resolved through `Controller/Tools/paths.py`. Discovery checks
  the explicit log path, the configured log directory, and both conventional
  Unreal log layouts below the selected server root.
- **Player snapshot:** `Runtime/player_characters.json` — enriched Steam player + character/inventory data fetched from the HTTP API.
- **HTTP API log:** `Logs/monitors/http_api/http_api.log` — rolling log of HTTP/API errors for troubleshooting.

---

## Configuration (with defaults)
All pulled from `config.get("monitor", {})` with sensible fallbacks.

- **Intervals & polling**
  - Every `state_refresh_seconds` — refresh the GUI state JSON and, if `track.http_api` is enabled, pull the latest HTTP API snapshot.
  - `monitor_heartbeat_interval_seconds` — default **300** (Discord heartbeat if enabled).
  - `wait_for_log_appearance_seconds` — default **120** (grace window for log to appear).
  - `tail_poll_interval_ms` — default **500** (tail loop sleep when idle).

- **Tracking toggles** (what to parse from the log)
  - `track.startup` (default **true**).
  - `track.auth` (default **true**).
  - `track.join` (default **true**).
  - `track.character` (default **true**).
  - `track.disconnect` (default **true**).
  - `track.autosave` (default **true**).
  - `track.crash` (default **true**).
  - `track.heartbeat` (default **true**).
  - `track.http_api` (default **true**) — poll the Vein HTTP API, copy structured status into the runtime state file, and refresh `Runtime/player_characters.json`.

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

> Notifications also require per-channel enablement through
> `Tools.discord.is_discord_channel_enabled(channel)`.

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
2. Immediately write the expected game-log path to stdout and runtime state.
   Packaged stdout is captured under `Logs/monitors/log_monitor/`, which feeds
   the GUI's Log Monitor tab.
3. Continue waiting when a clean server has not created its first log yet.
   After the configured grace window, diagnostics tell the operator to verify
   Quick Start paths instead of silently exiting.
4. Attach as soon as a candidate appears and mark the state as `tailing`.
5. Tail the file:
   - Detect truncation or replacement and reopen from the beginning.
   - If the server is offline, keep lightweight state available and pause HTTP
     polling until the server returns.
   - Every `state_refresh_seconds` → refresh the GUI state JSON and, if `track.http_api` is enabled, pull the latest HTTP API snapshot.
   - After each HTTP refresh, dump a rich `player_characters.json` snapshot (Steam IDs, names, characters, inventory) so the GUI can inspect players without hammering the API directly.
   - On **ready/joinable** signature → send “Server is up and joinable.”
   - On **auth** → “Auth OK for `<steam_id>`.”
   - On **join** → “`<name>` joined.” (track in a `current_players` set)
   - On **character select** → “`<name>` selected a character.”
   - On **disconnect** → “A player disconnected.”
   - On **autosave** → (debounced by `autosave_backup_cooldown_seconds`)
     - If `monitor.backups.on_autosave` → use the canonical `Tools.backups`
       backup engine.
     - Optional Discord: “Autosave detected — backup created.”
   - On **crash signature** → Discord alert: “Crash signature in log! Check server.”
   - On **heartbeat interval** (if enabled) → refresh state + optional Discord heartbeat.
6. Always on exit (finally) → mark inactive, remove PID file.

### `_write_logmon_state(...)`
Writes compact JSON status with a UTC timestamp. It explains whether the
monitor is waiting, tailing, idle because the server is offline, stopped, or
unable to read the selected file. Consumed by the GUI for status and path
diagnostics. It also includes:
- `http_api` payload when API polling is enabled (status/players/time/weather + last fetch/errors).
- `players` block summarising recently-seen players (steam_id, state, verification source, last log/http timestamps). This mirrors the more detailed `Runtime/player_characters.json` file.

### `Tools.paths.resolve_active_log()`
Chooses the source using configured and conventional app-managed paths. It can
also return the expected not-yet-created path for clean-install GUI watchers.

### `_refresh_http_api_state(client)` / `_update_player_character_snapshot(...)`
Fetch `/status`, `/players`, `/time`, `/weather` using `Controller/Tools/vein_http_api.py`, capture errors, and update the runtime HTTP payload. Player records are hydrated with `/players/:id` + `/characters/:id` calls, then written atomically to `Runtime/player_characters.json`. The helper also cross-references log-derived state so the GUI can show online/log-only players even when the API goes dark.

### `_discord(msg, channel="monitor")`
Sends a message to Discord only if that channel is enabled.

### Player timeline helpers
`_record_player_event`, `_player_state_payload`, `_flush_player_snapshot_if_needed`, etc., maintain a bounded cache (≈10 players) with log + HTTP events (`login`, `auth`, `join`, `character_select`, `disconnect`, `http_online/offline`). This cache feeds both the GUI tree and a standalone `Runtime/player_characters.json`.

---

## Discord Channels Used
- `monitor` — status, joinable, auth/join/character/disconnect, autosave, crash alerts, heartbeats (if enabled)

---

## Integration Points
- **GUI (vein_manager.py):**
  - Reads `log_monitor.state.json` (falling back to the legacy name) and `log_monitor.pid` to show live status.
  - Can create `stop_log_monitor.flag` to request a clean shutdown.
- **Controller/Tools/**:
  - `is_server_running()` to stop monitoring when server ends.
  - `send_discord_message()` for all outbound notifications.
  - `backup_save_file()` for autosave-triggered backups.
- **start_server.py:**
  - Spawns this monitor before the game process so first-boot lines are visible,
    depending on feature flags.

---

## Exit Conditions
- `stop_log_monitor.flag` file appears.
- Any unhandled exception (state and PID are still cleaned up in `finally`).

---

## Error/Safety Considerations
- Missing logs and offline servers use lightweight polling rather than a tight
  loop. A missing first log is not treated as a fatal error.
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
| Change monitored log source | Quick Start's advanced `game_log.override` |

---

_Last updated by AI code analysis for the Vein Server Management project._
