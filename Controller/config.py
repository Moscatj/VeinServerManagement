"""
config.py  — resilient loader for config.yaml (and legacy config.json)

Search order for config files:
  1) env VEIN_CONFIG (absolute path to a YAML or JSON file)
  2) <VEIN_MGMT_ROOT>\Config\config.yaml
  3) <VEIN_MGMT_ROOT>\Config\config.yml
  4) <VEIN_MGMT_ROOT>\Config\config.json
  5) <this file>\..\config.json                   (legacy: Controller\config.json)

Also honors env:
  - VEIN_MGMT_ROOT        -> forces the ServerManagement root
  - DISCORD_WEBHOOK_URL   -> universal webhook override
"""

from __future__ import annotations

from pathlib import Path
import os, json
from typing import Any, Dict

import yaml  # PyYAML (already used elsewhere)

_CONFIG_CACHE: Dict[str, Any] | None = None

# Toggle: create backup_root when missing
AUTO_CREATE_BACKUP_ROOT = True


def _mgmt_root() -> Path:
    # If user provided VEIN_MGMT_ROOT, trust it
    env = os.getenv("VEIN_MGMT_ROOT", "").strip()
    if env:
        return Path(env).resolve()

    # Default: this file lives in ...\ServerManagment\Controller\config.py
    controller_dir = Path(__file__).resolve().parent
    return controller_dir.parent  # -> ServerManagment


def _candidate_configs(mgmt_root: Path) -> list[Path]:
    env_cfg = os.getenv("VEIN_CONFIG", "").strip()
    cands: list[Path] = []
    if env_cfg:
        cands.append(Path(env_cfg))
    cands.append(mgmt_root / "Config" / "config.yaml")  # Try YAML first
    cands.append(mgmt_root / "Config" / "config.yml")
    cands.append(mgmt_root / "Config" / "config.json")
    cands.append(mgmt_root / "Controller" / "config.json")
    return [p for p in cands if str(p).strip()]


def _migrate_v2_layout(cfg: Dict[str, Any], mgmt_root: Path) -> Dict[str, Any]:
    """
    Bridge newer YAML layout (version >= 2) into the legacy flat keys expected
    by older code. This lets config.yaml drive everything without forcing a
    rewrite of all callers.

    The goal is:
      - Keep the structured sections (`paths`, `server`, `monitor`, `backup`)
      - Also synthesize top-level keys like `server_dir`, `save_dir`,
        `logs_dir`, `runtime_dir`, `backup_root`, `server_executables`, etc.
    """
    # If there is no structured layout, nothing to do.
    paths = cfg.get("paths") or {}
    server = cfg.get("server") or {}
    monitor_section = cfg.get("monitor")
    log_monitor_section = cfg.get("log_monitor")
    crash_monitor_section = cfg.get("crash_monitor")
    backups_section = cfg.get("backups") or cfg.get("backup") or {}
    steam_section = cfg.get("steam") or {}

    features = cfg.get("features")
    if not isinstance(features, dict):
        features = {}
        cfg["features"] = features

    if isinstance(paths, dict):
        path_map = {
            "server_root": "server_dir",
            "server_dir": "server_dir",
            "saves_dir": "save_dir",
            "save_dir": "save_dir",
            "logs_dir": "logs_dir",
            "runtime_dir": "runtime_dir",
            "absolute_log_file": "absolute_log_file",
            "mgmt_log_dir": "mgmt_log_dir",
            "backup_root": "backup_root",
        }
        for new_key, legacy_key in path_map.items():
            val = paths.get(new_key)
            if val and not cfg.get(legacy_key):
                cfg[legacy_key] = val

    # Map structured `server` block to legacy flat keys
    if isinstance(server, dict):
        exes = server.get("executables")
        if isinstance(exes, list) and not cfg.get("server_executables"):
            cfg["server_executables"] = exes

        pref = server.get("preferred_exe")
        if pref and not cfg.get("preferred_exe"):
            cfg["preferred_exe"] = pref

        ports = server.get("ports") or {}
        direct_keys = {
            "game": ("game_port", int),
            "query": ("query_port", int),
            "bind_ip": ("multi_home_ip", str),
        }
        for new_key, (legacy_key, cast) in direct_keys.items():
            val = ports.get(new_key)
            if val and not cfg.get(legacy_key):
                try:
                    cfg[legacy_key] = cast(val)
                except Exception:
                    cfg[legacy_key] = val

        max_players = server.get("max_players") or (server.get("options") or {}).get(
            "max_players"
        )
        if max_players and not cfg.get("max_players"):
            try:
                cfg["max_players"] = int(max_players)
            except Exception:
                cfg["max_players"] = max_players

        # Map simple passthrough keys if present
        simple_keys = [
            "headless_mode",
            "show_monitor_window",
            "multi_home_ip",
            "map_path",
            "extra_launch_args",
            "enable_query_port",
            "kill_ue_helpers_on_shutdown",
        ]
        for key in simple_keys:
            if key in server and not cfg.get(key):
                cfg[key] = server[key]

    # Merge structured `monitor` / `log_monitor` blocks and map legacy knobs
    monitor_combined = None
    if isinstance(monitor_section, dict):
        monitor_combined = dict(monitor_section)
    if isinstance(log_monitor_section, dict):
        monitor_combined = monitor_combined or {}
        monitor_combined.update(log_monitor_section)
    if monitor_combined is not None:
        cfg["monitor"] = monitor_combined
        cfg["log_monitor"] = monitor_combined
        monitor = monitor_combined
    else:
        monitor = monitor_section if isinstance(monitor_section, dict) else {}

    if isinstance(monitor, dict):
        hb = monitor.get("heartbeat_seconds") or monitor.get(
            "heartbeat_interval_seconds"
        )
        if hb and not cfg.get("monitor_heartbeat_interval_seconds"):
            try:
                cfg["monitor_heartbeat_interval_seconds"] = int(hb)
            except Exception:
                pass

        if "enabled" in monitor and "enable_log_monitor" not in features:
            features["enable_log_monitor"] = bool(monitor["enabled"])

        # Preserve structured monitor.discord for new code.
        # Older code mostly uses flat `discord_webhook`, handled separately.
        if "discord" in monitor and not cfg.get("monitor_discord"):
            cfg["monitor_discord"] = monitor["discord"]

    # Map structured crash_monitor block to legacy knobs
    crash_monitor = None
    if isinstance(crash_monitor_section, dict):
        crash_monitor = dict(crash_monitor_section)
        cfg["crash_monitor"] = crash_monitor
    else:
        crash_monitor = {}

    if crash_monitor:
        if "enabled" in crash_monitor and "enable_crash_monitor" not in features:
            features["enable_crash_monitor"] = bool(crash_monitor["enabled"])

        crash_map = {
            "heartbeat_seconds": "crash_monitor_interval_seconds",
            "idle_notify_minutes": "crash_monitor_idle_notify_minutes",
            "notify_debounce_seconds": "crash_notify_debounce_seconds",
            "crash_backoff_base": "crash_backoff_base",
            "crash_backoff_max_seconds": "crash_backoff_max_seconds",
            "crash_loop_max_attempts": "crash_loop_max_attempts",
            "crash_loop_window_minutes": "crash_loop_window_minutes",
            "crash_loop_cooldown_seconds": "crash_loop_cooldown_seconds",
            "shutdown_timeout_sec": "shutdown_timeout_sec",
            "restart_throttle_seconds": "restart_throttle_seconds",
        }
        for new_key, legacy_key in crash_map.items():
            if legacy_key in cfg:
                continue
            val = crash_monitor.get(new_key)
            if val is None:
                continue
            try:
                cfg[legacy_key] = int(val)
            except Exception:
                cfg[legacy_key] = val

        if (
            "stale_flag_delay_sec" in crash_monitor
            and "stale_flag_delay_sec" not in cfg
        ):
            cfg["stale_flag_delay_sec"] = crash_monitor["stale_flag_delay_sec"]

    # Map new backup layout to legacy globals where helpful
    backup_v2: Dict[str, Any] = {}
    if isinstance(backups_section, dict):
        backup_v2.update(backups_section)
    legacy_backup = cfg.get("backup")
    if isinstance(legacy_backup, dict):
        # legacy keys should not override the structured section
        for k, v in legacy_backup.items():
            backup_v2.setdefault(k, v)
    if backup_v2:
        cfg["backups"] = backup_v2
        cfg["backup"] = backup_v2

        enable_flag = backup_v2.get("enabled")
        if enable_flag is None:
            enable_flag = backup_v2.get("enable")
        if enable_flag is not None and "enable_backups" not in features:
            features["enable_backups"] = bool(enable_flag)

        root = backup_v2.get("root")
        if root and not cfg.get("backup_root"):
            cfg["backup_root"] = root

        # Older JSON used a top-level `backups` block; keep it if present.

    # Map structured steam block to legacy flat keys
    if isinstance(steam_section, dict):
        steam_path = steam_section.get("steamcmd_path")
        if steam_path and not cfg.get("steamcmd_path"):
            cfg["steamcmd_path"] = steam_path

        app_id = steam_section.get("app_id")
        if app_id and not cfg.get("app_id"):
            cfg["app_id"] = app_id

        auto_start = steam_section.get("auto_update_on_start")
        if auto_start is not None and "auto_update_on_start" not in cfg:
            cfg["auto_update_on_start"] = auto_start

        mapping = {
            "steam_update_validate": "steam_update_validate",
            "steam_update_beta": "steam_update_beta",
            "steam_update_beta_password": "steam_update_beta_password",
            "steam_update_retries": "steam_update_retries",
            "steam_update_timeout_seconds": "steam_update_timeout_seconds",
        }
        for new_key, legacy_key in mapping.items():
            if legacy_key in cfg:
                continue
            if new_key in steam_section:
                cfg[legacy_key] = steam_section[new_key]

    # Map lifecycle.startup/shutdown -> legacy flat knobs
    lifecycle = cfg.get("lifecycle") or {}
    if isinstance(lifecycle, dict):
        # --- STARTUP ---
        startup = lifecycle.get("startup") or {}
        if isinstance(startup, dict):
            sq = startup.get("startup_quiet_seconds")
            if sq is not None:
                try:
                    sq_int = int(sq)
                except Exception:
                    sq_int = None
                else:
                    # Prefer the structured monitor block for new code
                    mon = cfg.get("monitor") or {}
                    if "startup_quiet_seconds" not in mon:
                        mon["startup_quiet_seconds"] = sq_int
                    cfg["monitor"] = mon

                    # Also expose a flat key for older code
                    if not cfg.get("startup_quiet_seconds"):
                        cfg["startup_quiet_seconds"] = sq_int

        # --- SHUTDOWN ---
        shutdown = lifecycle.get("shutdown") or {}
        if isinstance(shutdown, dict):
            w = shutdown.get("warn_seconds")
            if w is not None and not cfg.get("pre_shutdown_warning_seconds"):
                try:
                    cfg["pre_shutdown_warning_seconds"] = int(w)
                except Exception:
                    pass

            fw = shutdown.get("final_warning_at")
            if fw is not None and not cfg.get("shutdown_final_warning_at"):
                try:
                    cfg["shutdown_final_warning_at"] = int(fw)
                except Exception:
                    pass

            gs = shutdown.get("grace_seconds")
            if gs is not None and not cfg.get("shutdown_grace_seconds"):
                try:
                    cfg["shutdown_grace_seconds"] = int(gs)
                except Exception:
                    pass

    # Ensure there is *some* server_dir so existing validation has a chance.
    if not cfg.get("server_dir"):
        # As an absolute last resort, assume the game lives under the
        # ServerManagement parent like before.
        guess = str(mgmt_root.parent / "VeinServer")
        cfg.setdefault("server_dir", guess)

    # Discord block can now express enable/disable
    discord_cfg = cfg.get("discord")
    if isinstance(discord_cfg, dict) and "enabled" in discord_cfg:
        features.setdefault("enable_discord", bool(discord_cfg["enabled"]))

    return cfg


def _with_defaults(cfg: Dict[str, Any], mgmt_root: Path) -> Dict[str, Any]:
    features = cfg.get("features") or {}
    cfg.setdefault("features", features)

    # Common toggles / cadences
    cfg.setdefault("monitor_heartbeat_interval_seconds", 300)
    cfg.setdefault("show_monitor_window", False)

    # Backups (global retention)
    cfg.setdefault("max_backups", 10)
    cfg.setdefault("backup_max_age_days", 7)

    # Server defaults
    cfg.setdefault("max_players", 8)
    cfg.setdefault("game_port", 7777)
    cfg.setdefault("query_port", 27015)
    cfg.setdefault("multi_home_ip", "0.0.0.0")

    # Behavior knobs
    cfg.setdefault("preboot_shutdown", True)
    cfg.setdefault("backup_on_detect", True)
    cfg.setdefault("shutdown_timeout_sec", 60)
    cfg.setdefault("restart_throttle_seconds", 120)

    # Executable candidates
    cfg.setdefault(
        "server_executables", ["VeinServer.exe", "VeinServer-Win64-Test.exe"]
    )

    # Default backup_root to ServerManagement\Backups if missing
    if not cfg.get("backup_root"):
        cfg["backup_root"] = str(mgmt_root / "Backups")

    # Optional: allow DISCORD_WEBHOOK_URL env var to override JSON
    env_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if env_webhook:
        cfg["discord_webhook"] = env_webhook

    return cfg


def _normalize_paths(cfg: Dict[str, Any], mgmt_root: Path) -> Dict[str, Any]:
    """Normalize key filesystem paths to absolute paths (prevents CWD surprises)."""

    base = Path(mgmt_root)

    def _abs(p: str | None) -> str | None:
        if not p or not isinstance(p, str):
            return p
        expanded = os.path.expandvars(os.path.expanduser(p))
        path = Path(expanded)
        if path.is_absolute():
            return str(path.resolve())
        return str((base / path).resolve())

    path_keys = [
        "server_dir",
        "backup_root",
        "steamcmd_path",
        "save_dir",
        "logs_dir",
        "mgmt_log_dir",
        "absolute_log_file",
        "runtime_dir",
    ]
    for k in path_keys:
        if cfg.get(k):
            cfg[k] = _abs(cfg[k])

    # Normalize nested backups block if present
    b = cfg.get("backups")
    if isinstance(b, dict):
        if b.get("root"):
            b["root"] = _abs(b["root"])
        if b.get("save_dir"):
            b["save_dir"] = _abs(b["save_dir"])
        cfg["backups"] = b

    # Normalize nested new backup layout's root too (if present)
    b2 = cfg.get("backup")
    if isinstance(b2, dict):
        if b2.get("root"):
            b2["root"] = _abs(b2["root"])
        cfg["backup"] = b2

    p = cfg.get("paths")
    if isinstance(p, dict):
        if p.get("save_dir"):
            p["save_dir"] = _abs(p["save_dir"])
        if p.get("saves_dir"):
            p["saves_dir"] = _abs(p["saves_dir"])
        if p.get("logs_dir"):
            p["logs_dir"] = _abs(p["logs_dir"])
        if p.get("mgmt_log_dir"):
            p["mgmt_log_dir"] = _abs(p["mgmt_log_dir"])
        if p.get("runtime_dir"):
            p["runtime_dir"] = _abs(p["runtime_dir"])
        if p.get("absolute_log_file"):
            p["absolute_log_file"] = _abs(p["absolute_log_file"])
        cfg["paths"] = p

    lm = cfg.get("log_monitor")
    if isinstance(lm, dict) and lm.get("state_file"):
        lm["state_file"] = _abs(lm["state_file"])
        cfg["log_monitor"] = lm

    cm = cfg.get("crash_monitor")
    if isinstance(cm, dict) and cm.get("state_file"):
        cm["state_file"] = _abs(cm["state_file"])
        cfg["crash_monitor"] = cm

    return cfg


def _resolve_discord_webhook(cfg: Dict[str, Any]) -> None:
    """
    Resolve the Discord webhook with clear precedence:
      1) If cfg['discord_webhook'] is 'ENV:NAME', use that environment variable.
      2) Else, use cfg['discord_webhook'] as a literal URL (if present).
      3) Else, leave Discord disabled.
    """
    val = cfg.get("discord_webhook")
    if not val:
        return

    if isinstance(val, str) and val.startswith("ENV:"):
        env_name = val.split(":", 1)[1].strip()
        env_val = os.getenv(env_name, "").strip()
        if env_val:
            cfg["discord_webhook"] = env_val
        else:
            print(
                f"[Config] Discord webhook env var '{env_name}' not set; disabling Discord."
            )
            cfg["discord_webhook"] = ""
    elif not isinstance(val, str):
        cfg["discord_webhook"] = ""


def _validate(cfg: Dict[str, Any]) -> None:
    problems: list[str] = []

    if not cfg.get("server_dir"):
        problems.append("server_dir is required but missing.")

    mp = cfg.get("map_path", "")
    if mp is None:
        print("[Config] map_path is None — using default project map (auto mode).")
        cfg["map_path"] = ""

    sd = cfg.get("server_dir")
    if sd and not os.path.isdir(sd):
        problems.append(f"server_dir does not exist: {sd}")

    br = cfg.get("backup_root")
    if br and not os.path.isdir(br):
        if AUTO_CREATE_BACKUP_ROOT:
            try:
                os.makedirs(br, exist_ok=True)
            except Exception:
                problems.append(
                    f"backup_root does not exist and could not be created: {br}"
                )
        else:
            problems.append(f"backup_root does not exist: {br}")

    # also validate/create nested backups.root (if using the v2 layout)
    b = cfg.get("backup")
    if isinstance(b, dict):
        br2 = b.get("root")
        if br2 and not os.path.isdir(br2):
            if AUTO_CREATE_BACKUP_ROOT:
                try:
                    os.makedirs(br2, exist_ok=True)
                except Exception:
                    problems.append(
                        f"backup.root does not exist and could not be created: {br2}"
                    )
            else:
                problems.append(f"backup.root does not exist: {br2}")

    # Ports
    for key in ("game_port", "query_port"):
        val = cfg.get(key)
        if val is not None:
            try:
                port = int(val)
                if not (1 <= port <= 65535):
                    problems.append(f"{key} out of range: {val}")
            except Exception:
                problems.append(f"{key} is not an integer: {val}")

    if problems:
        raise ValueError("Config validation failed:\n- " + "\n- ".join(problems))


def _load_first_existing(paths: list[Path]) -> tuple[Path, dict]:
    """
    Prefer YAML over JSON when both exist, but still allow either.
    The GUI can set VEIN_CONFIG to explicitly choose one.
    """
    # 1) Explicit path (GUI-selected)
    env_path = os.environ.get("VEIN_CONFIG")
    if env_path and Path(env_path).exists():
        p = Path(env_path)
        with p.open("r", encoding="utf-8") as f:
            data = (
                yaml.safe_load(f)
                if p.suffix.lower() in (".yaml", ".yml")
                else json.load(f)
            )
        return p, data or {}

    # 2) Fallback discovery
    yaml_paths = [p for p in paths if p.suffix.lower() in (".yaml", ".yml")]
    json_paths = [p for p in paths if p.suffix.lower() == ".json"]

    for p in yaml_paths + json_paths:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = (
                    yaml.safe_load(f)
                    if p.suffix.lower() in (".yaml", ".yml")
                    else json.load(f)
                )
            return p, data or {}

    raise FileNotFoundError(
        "No config file found. Tried:\n  " + "\n  ".join(str(p) for p in paths)
    )


def load_config() -> Dict[str, Any]:
    """
    Load and cache the active config file (YAML or JSON).

    This function is the single source of truth for the *flat* config view
    that the rest of the tools use. Newer structured layouts in config.yaml
    (version >= 2) are migrated to legacy keys here so older code keeps
    working without modification.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    mgmt = _mgmt_root()
    cfg_path, cfg = _load_first_existing(_candidate_configs(mgmt))

    # Bridge newer structured layouts into the legacy flat keys
    cfg = _migrate_v2_layout(cfg, mgmt)

    # Minimal critical checks / conveniences before defaults
    if not cfg.get("server_dir"):
        raise ValueError(f"{cfg_path}: 'server_dir' is required")

    cfg = _with_defaults(cfg, mgmt)
    cfg = _normalize_paths(cfg, mgmt)
    _resolve_discord_webhook(cfg)
    _validate(cfg)

    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE
