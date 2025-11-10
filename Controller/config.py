"""
config.py  — resilient loader for config.ymal (legacy config.json)

Search order for config.json:
  1) env VEIN_CONFIG (absolute path to a json file)
  2) <VEIN_MGMT_ROOT>\Config\config.json
  3) <this file>\..\config.json                   (legacy: Controller\config.json)

Also honors env:
  - VEIN_MGMT_ROOT  -> forces the ServerManagment root
  - DISCORD_WEBHOOK_URL  -> universal webhook override
"""

from __future__ import annotations
import json, os, yaml
from pathlib import Path
from typing import Any, Dict

_CONFIG_CACHE: Dict[str, Any] | None = None

# Toggle: create backup_root when missing
AUTO_CREATE_BACKUP_ROOT = True


def _mgmt_root() -> Path:
    # If user provided VEIN_MGMT_ROOT, trust it
    env = os.getenv("VEIN_MGMT_ROOT", "").strip()
    if env:
        return Path(env).resolve()

    # Default: this file lives in ...\ServerManagmen t\Controller\config.py
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
    cands.append((mgmt_root / "Controller" / "config.json")) 
    return [p for p in cands if str(p).strip()]


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
    cfg.setdefault("server_executables", ["VeinServer.exe", "VeinServer-Win64-Test.exe"])

    # Default backup_root to ServerManagment\Backups if missing
    if not cfg.get("backup_root"):
        cfg["backup_root"] = str(mgmt_root / "Backups")

    # Optional: allow DISCORD_WEBHOOK_URL env var to override JSON
    env_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if env_webhook:
        cfg["discord_webhook"] = env_webhook

    return cfg


def _normalize_paths(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize key filesystem paths to absolute paths (prevents CWD surprises)."""
    def _abs(p: str | None) -> str | None:
        if not p or not isinstance(p, str):
            return p
        return os.path.abspath(os.path.normpath(p))

    path_keys = [
        "server_dir", "backup_root", "steamcmd_path",
        "save_dir", "logs_dir", "absolute_log_file",
    ]
    for k in path_keys:
        if cfg.get(k):
            cfg[k] = _abs(cfg[k])

    # normalize nested paths
    b = cfg.get("backups")
    if isinstance(b, dict):
        if b.get("root"):     b["root"] = _abs(b["root"])
        if b.get("save_dir"): b["save_dir"] = _abs(b["save_dir"])
        cfg["backups"] = b

    p = cfg.get("paths")
    if isinstance(p, dict):
        if p.get("save_dir"): p["save_dir"] = _abs(p["save_dir"])
        if p.get("logs_dir"): p["logs_dir"] = _abs(p["logs_dir"])
        cfg["paths"] = p
    return cfg


def _resolve_discord_webhook(cfg: Dict[str, Any]) -> None:
    """
    Resolve the Discord webhook with clear precedence:
      1) If cfg['discord_webhook'] is 'ENV:NAME', use that environment variable.
      2) Else if DISCORD_WEBHOOK_URL is set, use that.
      3) Else leave empty/None.
    If Discord is enabled but we end up without a usable URL, auto-disable Discord.
    """
    features = cfg.get("features", {})
    raw = (cfg.get("discord_webhook") or "").strip()

    if raw.upper().startswith("ENV:"):
        var_name = raw.split(":", 1)[1].strip()
        env_val = os.getenv(var_name, "").strip()
        cfg["discord_webhook"] = env_val  # may be empty
    else:
        env_val = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        if env_val:
            cfg["discord_webhook"] = env_val

    if features.get("enable_discord", True) and not cfg.get("discord_webhook"):
        features["enable_discord"] = False
        cfg["features"] = features
        print("[Config] Discord enabled, but no webhook found; disabling Discord.")


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
                problems.append(f"backup_root does not exist and could not be created: {br}")
        else:
            problems.append(f"backup_root does not exist: {br}")

    # also validate/create nested backups.root
    b = cfg.get("backups")
    if isinstance(b, dict):
        br2 = b.get("root")
        if br2 and not os.path.isdir(br2):
            if AUTO_CREATE_BACKUP_ROOT:
                try:
                    os.makedirs(br2, exist_ok=True)
                except Exception:
                    problems.append(f"backups.root does not exist and could not be created: {br2}")
            else:
                problems.append(f"backups.root does not exist: {br2}")

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
            data = yaml.safe_load(f) if p.suffix.lower() in (".yaml", ".yml") else json.load(f)
        return p, data or {}

    # 2) Fallback discovery
    yaml_paths = [p for p in paths if p.suffix.lower() in (".yaml", ".yml")]
    json_paths = [p for p in paths if p.suffix.lower() == ".json"]

    # Prefer first existing YAML
    for p in yaml_paths + json_paths:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) if p.suffix.lower() in (".yaml", ".yml") else json.load(f)
            return p, data or {}

    raise FileNotFoundError("No configuration file found in: " + " | ".join(str(p) for p in paths))


def load_config() -> Dict[str, Any]:
    """Load and cache config.json; raise if missing/invalid."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    mgmt = _mgmt_root()
    cfg_path, cfg = _load_first_existing(_candidate_configs(mgmt))

    # Minimal critical checks / conveniences before defaults
    if not cfg.get("server_dir"):
        raise ValueError(f"{cfg_path}: 'server_dir' is required")

    cfg = _with_defaults(cfg, mgmt)
    cfg = _normalize_paths(cfg)
    _resolve_discord_webhook(cfg)
    _validate(cfg)

    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE
