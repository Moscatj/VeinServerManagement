# config.py — Summary  
**Vein Server Management Suite**

---

## Purpose
`config.py` is the **resilient loader** and validator for `config.json`.  
It provides a consistent entry point for all controllers and utilities that need access to configuration data.

This module:
- Finds the correct `config.json` using multiple fallbacks.
- Normalizes and validates paths and settings.
- Applies sensible defaults for missing fields.
- Resolves Discord webhook overrides.
- Creates missing backup folders if needed.
- Caches configuration in memory for reuse across imports.

---

## Search Order for config.json
1. Environment variable **`VEIN_CONFIG`** — absolute path to JSON file.  
2. `<VEIN_MGMT_ROOT>\Config\config.json` — preferred default location.  
3. `<ServerManagment\Controller\config.json` — legacy fallback.  

Also respects environment variables:
- `VEIN_MGMT_ROOT` → defines the Server Management root.  
- `DISCORD_WEBHOOK_URL` → global webhook override.  

---

## Key Globals
| Name | Description |
|------|--------------|
| `_CONFIG_CACHE` | In-memory cache of last-loaded configuration. Prevents repeated reads. |
| `AUTO_CREATE_BACKUP_ROOT` | If `True`, creates `Backups/` directory automatically if missing. |

---

## Main Internal Functions

### `_mgmt_root()`
Determines the management root directory:
- If `VEIN_MGMT_ROOT` is set → returns it.
- Else infers from this file’s location (`Controller/..`).

### `_candidate_configs(mgmt_root)`
Builds the list of possible config paths to try in priority order.

### `_with_defaults(cfg, mgmt_root)`
Injects sane defaults for missing or empty values, such as:
- `monitor_heartbeat_interval_seconds` = 300  
- `show_monitor_window` = False  
- `max_backups` = 10  
- `backup_max_age_days` = 7  
- `max_players` = 8  
- `game_port` = 7777  
- `query_port` = 27015  
- `multi_home_ip` = "0.0.0.0"  
- `preboot_shutdown` = True  
- `backup_on_detect` = True  
- `shutdown_timeout_sec` = 60  
- `restart_throttle_seconds` = 120  
- `server_executables` = ["VeinServer.exe", "VeinServer-Win64-Test.exe"]  
- `backup_root` = `<ServerManagment>\Backups` (if missing)

Also applies `DISCORD_WEBHOOK_URL` from the environment if present.

---

### `_normalize_paths(cfg)`
Ensures all filesystem paths are **absolute and OS-safe**:
- Normalizes path separators.
- Expands relative paths.
- Applies to keys such as `server_dir`, `backup_root`, `steamcmd_path`, `save_dir`, `logs_dir`, and `absolute_log_file`.

Prevents issues with relative CWD or mixed slash/backslash usage.

---

### `_resolve_discord_webhook(cfg)`
Determines which Discord webhook URL to use:
1. If `cfg["discord_webhook"]` starts with `"ENV:NAME"`, reads that environment variable.  
2. Else if `DISCORD_WEBHOOK_URL` is set, uses it.  
3. Else keeps the JSON value or leaves empty.

If Discord is enabled but no usable webhook exists, automatically disables Discord with a warning.

---

### `_validate(cfg)`
Performs full validation and auto-correction:
- Ensures `server_dir` exists.
- Creates `backup_root` if missing (if `AUTO_CREATE_BACKUP_ROOT` is True).
- Checks `game_port` and `query_port` are integers within 1–65535.
- Ensures `map_path` is not None (sets to empty if it is).
- Accumulates and raises all validation errors in one message.

---

### `_load_first_existing(paths)`
Attempts to load the first valid JSON file in the candidate list.
Raises a `FileNotFoundError` if none exist.

---

### `load_config()`
Primary public entry point:
1. Returns cached config if already loaded.
2. Detects management root (`_mgmt_root()`).
3. Finds candidate configs (`_candidate_configs()`).
4. Loads the first valid one.
5. Applies `_with_defaults()`, `_normalize_paths()`, `_resolve_discord_webhook()`, `_validate()`.
6. Caches the final dictionary in `_CONFIG_CACHE`.

---

## Example Usage
Typical import and access pattern used throughout the suite:
    from config import load_config
    cfg = load_config()
    print(cfg["server_dir"])

This ensures all paths and defaults are applied before use.

---

## Integration Points
| Module | Uses |
|---------|------|
| `config_helper.py` | Imports `load_config()` and exposes convenient getters. |
| `start_server.py` | Validates and reads path, port, and executable list. |
| `utils.py` | Reads config for feature toggles, backups, logging, and Steam update behavior. |
| `vein_manager.py` | GUI configuration editor and viewer. |
| `shutdown_server.py` | Reads for quiet window and shutdown countdown. |
| `monitor_log.py` / `crash_monitor.py` | Reads monitoring cadence and tracking toggles. |

---

## Behavior & Safety
- Graceful handling of missing or malformed JSON.
- Environment variable overrides allow dynamic configuration.
- Caches configuration to improve performance and consistency.
- Optional automatic directory creation for backups.
- Defensive defaults ensure server can start even with minimal config.

---

_Last updated by AI code analysis for the Vein Server Management project._
