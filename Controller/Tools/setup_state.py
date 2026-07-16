"""Pure setup-workflow classification for installer and GUI routing."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


SETUP_SCHEMA_VERSION = 1


class SetupState(str, Enum):
    NEW_OR_MISSING = "new_or_missing"
    FIRST_SETUP = "first_setup"
    EXISTING_UNREGISTERED = "existing_unregistered"
    CONFIGURED = "configured"
    REPAIR_MISSING = "repair_missing"
    AMBIGUOUS = "ambiguous"


class SetupWorkflow(str, Enum):
    NEW_SERVER = "new_server"
    FIRST_SETUP = "first_setup"
    EXISTING_SERVER = "existing_server"


NEW_SERVER_SOURCES = {"installer_new", "quick_start_new"}
KNOWN_SETUP_SOURCES = NEW_SERVER_SOURCES | {
    "existing_import",
    "manual",
    "unconfigured",
    "unknown",
}


@dataclass(frozen=True)
class SetupMetadata:
    schema_version: int = SETUP_SCHEMA_VERSION
    completed: bool = False
    server_root: str = ""
    source: str = "unconfigured"
    completed_at: str = ""

    @classmethod
    def from_config(cls, config: Mapping[str, Any] | None) -> "SetupMetadata":
        raw = config.get("setup") if isinstance(config, Mapping) else None
        if not isinstance(raw, Mapping):
            return cls()
        try:
            schema_version = int(raw.get("schema_version", SETUP_SCHEMA_VERSION))
        except (TypeError, ValueError):
            schema_version = SETUP_SCHEMA_VERSION
        source = str(raw.get("source") or "unknown").strip().lower()
        if source not in KNOWN_SETUP_SOURCES:
            source = "unknown"
        return cls(
            schema_version=schema_version,
            completed=bool(raw.get("completed", False)),
            server_root=str(raw.get("server_root") or "").strip(),
            source=source,
            completed_at=str(raw.get("completed_at") or "").strip(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "completed": self.completed,
            "server_root": self.server_root,
            "source": self.source,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class SetupAssessment:
    state: SetupState
    workflow: SetupWorkflow
    primary_action: str
    reason: str


def normalize_server_root(value: str | Path | None, *, base_dir: str | Path | None = None) -> str:
    """Normalize a configured root for durable, case-insensitive comparison."""
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir).expanduser() / path
    return os.path.normcase(os.path.abspath(str(path))).rstrip("\\/")


def _roots_match(
    configured_root: str | Path,
    metadata_root: str | Path,
    *,
    base_dir: str | Path | None,
) -> bool:
    current = normalize_server_root(configured_root, base_dir=base_dir)
    recorded = normalize_server_root(metadata_root, base_dir=base_dir)
    return bool(current and recorded and current == recorded)


def classify_setup_state(
    *,
    server_root: str | Path,
    binaries_present: bool,
    meaningful_config_present: bool,
    metadata: SetupMetadata | Mapping[str, Any] | None = None,
    base_dir: str | Path | None = None,
) -> SetupAssessment:
    """Choose one operator workflow without equating binaries with configuration."""
    setup = metadata if isinstance(metadata, SetupMetadata) else SetupMetadata.from_config(metadata)
    root_matches = _roots_match(server_root, setup.server_root, base_dir=base_dir)

    if setup.completed and not root_matches:
        return SetupAssessment(
            SetupState.AMBIGUOUS,
            SetupWorkflow.EXISTING_SERVER,
            "Choose Server Intent",
            "The completed setup record belongs to a different server root.",
        )

    if setup.completed:
        if binaries_present:
            return SetupAssessment(
                SetupState.CONFIGURED,
                SetupWorkflow.EXISTING_SERVER,
                "Edit Server Settings",
                "This server root has completed setup and its binaries are available.",
            )
        return SetupAssessment(
            SetupState.REPAIR_MISSING,
            SetupWorkflow.NEW_SERVER,
            "Repair Missing Server",
            "Setup is complete, but the server binaries are missing.",
        )

    if not binaries_present:
        return SetupAssessment(
            SetupState.NEW_OR_MISSING,
            SetupWorkflow.NEW_SERVER,
            "Install Server",
            "No supported server executable is available and setup is incomplete.",
        )

    if setup.source in NEW_SERVER_SOURCES:
        return SetupAssessment(
            SetupState.FIRST_SETUP,
            SetupWorkflow.FIRST_SETUP,
            "Finish Server Setup",
            "The server was provisioned as new, but configuration is not complete.",
        )

    if meaningful_config_present:
        return SetupAssessment(
            SetupState.EXISTING_UNREGISTERED,
            SetupWorkflow.EXISTING_SERVER,
            "Import Existing Server",
            "Server binaries and meaningful configuration were found without a completion record.",
        )

    return SetupAssessment(
        SetupState.FIRST_SETUP,
        SetupWorkflow.FIRST_SETUP,
        "Finish Server Setup",
        "Server binaries exist, but no meaningful server configuration was detected.",
    )


def setup_metadata_update(
    server_root: str | Path,
    *,
    source: str,
    completed: bool,
    completed_at: str | None = None,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Build the structured config block written by installer/setup transitions."""
    normalized_source = str(source or "unknown").strip().lower()
    if normalized_source not in KNOWN_SETUP_SOURCES:
        raise ValueError(f"Unsupported setup source: {source}")
    timestamp = completed_at
    if completed and not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()
    if not completed:
        timestamp = ""
    return SetupMetadata(
        completed=completed,
        server_root=normalize_server_root(server_root, base_dir=base_dir),
        source=normalized_source,
        completed_at=str(timestamp or ""),
    ).as_dict()
