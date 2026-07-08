"""Read-only server preflight helpers for the Vein Manager GUI."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Iterable

from PySide6 import QtCore

from Tools.server_config_validator import ServerConfigCheck, summarize, validate_server_config


class PreflightSignals(QtCore.QObject):
    ready = QtCore.Signal(dict)


def summarize_preflight(results: Iterable[ServerConfigCheck]) -> dict:
    checks = list(results)
    counts = summarize(checks)
    problems = [item for item in checks if item.status in {"FAIL", "WARN", "INFO"}]
    if counts.get("FAIL", 0):
        headline = f"{counts['FAIL']} failure(s), {counts['WARN']} warning(s)"
    elif counts.get("WARN", 0):
        headline = f"{counts['WARN']} warning(s)"
    elif counts.get("INFO", 0):
        headline = f"{counts['INFO']} optional note(s)"
    else:
        headline = "All server preflight checks passed"
    return {
        "summary": counts,
        "headline": headline,
        "problems": [item.as_dict() for item in problems[:5]],
        "results": [item.as_dict() for item in checks],
    }


def load_config_for_preflight(config_path: str | os.PathLike) -> dict[str, Any]:
    """Load one config file without mutating process-wide config env/cache."""
    path = Path(config_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raw = {}

    import config as config_module

    mgmt_root = config_module._mgmt_root()
    cfg = config_module._migrate_v2_layout(dict(raw), mgmt_root)
    if not cfg.get("server_dir"):
        raise ValueError(f"{path}: 'server_dir' is required")
    cfg = config_module._with_defaults(cfg, mgmt_root)
    cfg = config_module._resolve_env_values(cfg)
    cfg = config_module._normalize_paths(cfg, mgmt_root)
    config_module._resolve_discord_webhook(cfg)
    config_module._validate(cfg)
    return cfg


class PreflightWorker(QtCore.QRunnable):
    """Run server install/config validation off the Qt UI thread."""

    def __init__(self, config_path: str | os.PathLike):
        super().__init__()
        self.config_path = Path(config_path)
        self.signals = PreflightSignals()

    def run(self) -> None:
        payload: dict
        try:
            cfg = load_config_for_preflight(self.config_path)
            payload = summarize_preflight(validate_server_config(cfg))
        except Exception as exc:
            payload = {
                "summary": {"PASS": 0, "INFO": 0, "WARN": 0, "FAIL": 1},
                "headline": "Preflight failed to run",
                "problems": [
                    {
                        "name": "server.preflight",
                        "status": "FAIL",
                        "message": str(exc),
                    }
                ],
                "results": [],
            }

        self.signals.ready.emit(payload)
