"""Guarded management-config editing for operator-facing backup policy."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class BackupPolicy:
    enabled: bool = True
    on_autosave: bool = False
    on_crash_detect: bool = True
    on_shutdown: bool = True
    cleanup_enabled: bool = True
    cleanup_by_count: bool = True
    cleanup_by_age: bool = True
    minimum_backups: int = 3
    max_backups: int = 10
    max_age_days: int = 7

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackupPolicyApplyResult:
    changed: bool
    backup: str
    policy: BackupPolicy

    def as_dict(self) -> dict[str, Any]:
        return {
            "changed": self.changed,
            "backup": self.backup,
            "policy": self.policy.as_dict(),
        }


def _trigger_value(triggers: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = triggers.get(key)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, Mapping):
        if "enabled" in raw:
            return bool(raw["enabled"])
        if "save_backup" in raw:
            return bool(raw["save_backup"])
    return default


def _mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Management configuration must contain a YAML mapping.")
    return data


def backup_policy_from_mapping(data: Mapping[str, Any]) -> BackupPolicy:
    backups = data.get("backups") or {}
    if not isinstance(backups, Mapping):
        backups = {}
    triggers = backups.get("triggers") or {}
    if not isinstance(triggers, Mapping):
        triggers = {}
    retention = backups.get("retention") or {}
    default_retention = retention.get("default") if isinstance(retention, Mapping) else {}
    if not isinstance(default_retention, Mapping):
        default_retention = {}
    enabled = backups.get("enabled", backups.get("enable", True))
    max_backups = int(
        default_retention.get("max_backups", backups.get("max_backups", 10))
    )
    max_age_days = int(
        default_retention.get(
            "max_age_days", backups.get("backup_max_age_days", 7)
        )
    )
    return BackupPolicy(
        enabled=bool(enabled),
        on_autosave=_trigger_value(triggers, "on_autosave", False),
        on_crash_detect=_trigger_value(triggers, "on_crash_detect", True),
        on_shutdown=_trigger_value(triggers, "shutdown", True),
        cleanup_enabled=bool(default_retention.get("enabled", True)),
        cleanup_by_count=bool(default_retention.get("by_count", True)),
        cleanup_by_age=bool(default_retention.get("by_age", True)),
        minimum_backups=int(
            default_retention.get("minimum_backups", min(3, max_backups))
        ),
        max_backups=max_backups,
        max_age_days=max_age_days,
    )


def validate_backup_policy(policy: BackupPolicy) -> None:
    if not 1 <= int(policy.minimum_backups) <= 10000:
        raise ValueError("Minimum retained backups must be between 1 and 10,000.")
    if not 1 <= int(policy.max_backups) <= 10000:
        raise ValueError("Backup count retention must be between 1 and 10,000.")
    if policy.cleanup_by_count and policy.max_backups < policy.minimum_backups:
        raise ValueError(
            "Maximum backups cannot be lower than the minimum retained backups."
        )
    if not 1 <= int(policy.max_age_days) <= 3650:
        raise ValueError("Backup age retention must be between 1 and 3,650 days.")


def load_backup_policy(config_path: str | Path) -> BackupPolicy:
    path = Path(config_path).expanduser()
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Backup Policy editing requires the primary YAML configuration.")
    policy = backup_policy_from_mapping(_mapping(path))
    validate_backup_policy(policy)
    return policy


def backup_policy_summary(policy: BackupPolicy) -> str:
    state = "enabled" if policy.enabled else "disabled"
    triggers = [
        label
        for label, enabled in (
            ("Autosave", policy.on_autosave),
            ("Crash", policy.on_crash_detect),
            ("Shutdown", policy.on_shutdown),
        )
        if enabled
    ]
    trigger_text = ", ".join(triggers) if triggers else "none"
    cleanup_modes = []
    if policy.cleanup_by_count:
        cleanup_modes.append(f"maximum {policy.max_backups} archive(s) per type")
    if policy.cleanup_by_age:
        cleanup_modes.append(f"maximum age {policy.max_age_days} day(s)")
    cleanup = (
        " and ".join(cleanup_modes)
        if policy.cleanup_enabled and cleanup_modes
        else "disabled"
    )
    active_note = "" if policy.enabled else " All subordinate actions are inactive."
    return (
        f"Backups {state}; saved triggers: {trigger_text}; automatic cleanup: "
        f"{cleanup}; always keep at least {policy.minimum_backups} per type."
        f"{active_note}"
    )


def _load_round_trip(path: Path) -> tuple[Any, Any | None]:
    try:
        from ruamel.yaml import YAML

        engine = YAML(typ="rt", pure=True)
        engine.preserve_quotes = True
        document = engine.load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(document, Mapping):
            raise ValueError("Management configuration must contain a YAML mapping.")
        return document, engine
    except ImportError:
        return _mapping(path), None


def _dump_document(document: Any, engine: Any | None) -> str:
    if engine is None:
        return yaml.safe_dump(dict(document), sort_keys=False, allow_unicode=True)
    stream = StringIO()
    engine.dump(document, stream)
    return stream.getvalue()


def _config_backup_root(config_path: Path, document: Mapping[str, Any]) -> Path:
    backups = document.get("backups") or {}
    raw = backups.get("root") if isinstance(backups, Mapping) else None
    root = Path(str(raw or "Backups")).expanduser()
    if not root.is_absolute():
        root = config_path.parent.parent / root
    return root / "Configs"


def apply_backup_policy(
    config_path: str | Path, policy: BackupPolicy
) -> BackupPolicyApplyResult:
    """Back up, atomically update, and post-validate supported backup policy."""
    validate_backup_policy(policy)
    path = Path(config_path).expanduser()
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Backup Policy editing requires the primary YAML configuration.")
    document, engine = _load_round_trip(path)
    current = backup_policy_from_mapping(document)
    if current == policy:
        return BackupPolicyApplyResult(False, "", policy)

    backups = document.get("backups")
    if not isinstance(backups, Mapping):
        document["backups"] = {}
        backups = document["backups"]
    backups["enabled"] = bool(policy.enabled)
    if "enable" in backups:
        backups["enable"] = bool(policy.enabled)
    triggers = backups.get("triggers")
    if not isinstance(triggers, Mapping):
        backups["triggers"] = {}
        triggers = backups["triggers"]
    triggers["on_autosave"] = bool(policy.on_autosave)
    triggers["on_crash_detect"] = bool(policy.on_crash_detect)
    shutdown = triggers.get("shutdown")
    if not isinstance(shutdown, Mapping):
        shutdown = {}
        triggers["shutdown"] = shutdown
    shutdown["enabled"] = bool(policy.on_shutdown)
    shutdown["save_backup"] = bool(policy.on_shutdown)
    retention = backups.get("retention")
    if not isinstance(retention, Mapping):
        retention = {}
        backups["retention"] = retention
    default_retention = retention.get("default")
    if not isinstance(default_retention, Mapping):
        default_retention = {}
        retention["default"] = default_retention
    default_retention["max_backups"] = int(policy.max_backups)
    default_retention["max_age_days"] = int(policy.max_age_days)
    default_retention["minimum_backups"] = int(policy.minimum_backups)
    default_retention["enabled"] = bool(policy.cleanup_enabled)
    default_retention["by_count"] = bool(policy.cleanup_by_count)
    default_retention["by_age"] = bool(policy.cleanup_by_age)

    text = _dump_document(document, engine)
    yaml.safe_load(text)
    backup_dir = _config_backup_root(path, document)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    backup = backup_dir / f"{path.stem}-backup-policy-{stamp}{path.suffix}"
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
        loaded = load_backup_policy(path)
        if loaded != policy:
            raise ValueError("Saved backup policy did not pass post-write validation.")
    except Exception:
        temp.unlink(missing_ok=True)
        rollback = path.with_suffix(path.suffix + ".rollback.tmp")
        rollback.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        os.replace(rollback, path)
        raise
    return BackupPolicyApplyResult(True, str(backup), policy)
