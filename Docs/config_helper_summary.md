# config_helper.py — Summary
**Vein Server Management Suite**

---

## Purpose
`config_helper.py` provides ergonomic, centralized access to the loaded `config.json` file.  
It ensures all controllers read configuration values consistently and safely, with correct types and
feature-gating logic.  

This module loads configuration **once on import** and exposes helper functions for:
- Typed key retrieval (`bool`, `int`, `list`, `dict`, `path`)
- Feature toggles
- Discord-channel enablement
- Normalized path resolution (absolute + OS-safe)

All other controllers (start_server, crash_monitor, monitor_log, GUI, etc.) depend on it for configuration access.

---

## Initialization
Example:
    config = load_config()
    features = config.get("features", {})

- `load_config()` comes from `config.py` and reads/parses the JSON config file.
- `features` is a shortcut to `config["features"]`, containing boolean flags and Discord channel toggles.

---

## Key Responsibilities

### 1. Feature Gates
    def is_feature_enabled(feature_key: str, default=True) -> bool
- Returns `True`/`False` based on `features[feature_key]`.
- Used to gate optional subsystems (log monitor, crash monitor, Steam updates, etc.).
- Falls back to `default` if the key is missing.

    def is_discord_channel_enabled(channel: str) -> bool
- Checks both global `enable_discord` and per-channel feature keys:
  - Example keys: `discord_startup`, `discord_monitor`, `discord_crash_monitor`, `discord_backups`
- Returns `False` if global Discord is disabled.
- Ensures consistent gating for all Discord notifications across the suite.

---

### 2. Typed Getters
Safe conversion helpers to avoid crashes when values are missing or mis-typed.

| Function | Return Type | Behavior |
|-----------|--------------|----------|
| `get_bool(key, default=False)` | bool | Returns True/False from any truthy/falsy config value. |
| `get_int(key, default=0)` | int | Parses numeric strings, coerces invalid entries to default. |
| `get_list(key, default=None)` | list | Returns list if present, else returns a copy of default (never None). |
| `get_dict(key, default=None)` | dict | Returns dict if present, else an empty dict. |

These guarantee the correct type even when users misconfigure JSON values.

---

### 3. Path Normalization
    def get_path(key: str) -> str
- Retrieves and normalizes file system paths:
  - Expands to absolute paths
  - Normalizes OS-specific separators
- Returns an empty string if the value isn’t a string.
- Prevents double-slashes or relative path issues between scripts.

Used by controllers for:
- `server_dir`
- `save_dir`
- `runtime_dir`
- `log_dir`
- any other configurable path keys.

---

## Integration Points
| Script | Usage |
|---------|-------|
| start_server.py | Reads server_dir, server_executables, feature flags (enable_crash_monitor, etc.) |
| monitor_log.py | Reads monitor intervals and monitor.track.* / monitor.notify.* values |
| crash_monitor.py | Reads crash_monitor_interval_seconds, crash_monitor_idle_notify_minutes |
| shutdown_server.py | Uses for optional pre-shutdown warnings and quiet-window lengths |
| vein_manager.py | GUI editor loads and saves config values through this module |
| utils.py | References features to decide which subsystems to start (backups, monitors, Discord, etc.) |

---

## Design Notes
- Immutable shared config: loaded once at import time; all modules read from the same in-memory object.
- Fail-safe conversions: no getter raises an exception; every one returns a valid default type.
- Platform-safe paths: always absolute, normalized with `os.path.normpath()` and `os.path.abspath()`.
- Feature consistency: `is_feature_enabled()` and `is_discord_channel_enabled()` centralize conditional logic,
  so toggles behave the same everywhere.

---

## Example Usage
    from config_helper import get_path, is_feature_enabled

    server_dir = get_path("server_dir")
    if is_feature_enabled("enable_log_monitor"):
        print("Starting log monitor…")

---

## Quick Reference
| Task | Function |
|------|-----------|
| Boolean feature toggle | is_feature_enabled() |
| Discord channel toggle | is_discord_channel_enabled() |
| Boolean config value | get_bool() |
| Integer config value | get_int() |
| List config value | get_list() |
| Dict config value | get_dict() |
| Normalized path | get_path() |

---

_Last updated by AI code analysis for the Vein Server Management project._
