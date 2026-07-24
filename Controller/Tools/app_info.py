"""Application identity and version helpers for the management suite."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


APP_DISPLAY_NAME = "Vein Server Management Suite"
APP_GUI_NAME = "Vein Server Manager"
APP_PUBLISHER = "Vein Server Management Contributors"
APP_LICENSE = "Non-Commercial Source Available"
APP_REPOSITORY = "https://github.com/Moscatj/VeinServerManagement"
VERSION_FILE = "version.txt"
UNKNOWN_VERSION = "0.0.0-dev"
STABLE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _read_version_file(root: Path) -> str | None:
    try:
        value = (root / VERSION_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _git_value(root: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (proc.stdout or "").strip()
    return value if proc.returncode == 0 and value else None


def get_app_version(root: Path, *, allow_git: bool = False) -> str:
    """Return the packaged or source version shown in the GUI."""
    for key in ("VEIN_APP_VERSION", "VEIN_PACKAGE_VERSION", "PACKAGE_VERSION"):
        value = os.environ.get(key, "").strip()
        if value:
            return value[1:] if value.lower().startswith("v") else value

    file_version = _read_version_file(root)
    if file_version:
        return file_version

    git_version = (
        _git_value(root, "describe", "--tags", "--dirty", "--always")
        if allow_git
        else None
    )
    return git_version or UNKNOWN_VERSION


def get_commit(root: Path, *, allow_git: bool = False) -> str:
    value = _git_value(root, "rev-parse", "--short", "HEAD") if allow_git else None
    return value or "unknown"


def release_notes_url(
    version: str,
    *,
    repository: str = APP_REPOSITORY,
) -> str:
    """Return exact release notes for a stable version or the latest release."""

    normalized = str(version or "").strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]
    base = repository.rstrip("/")
    if STABLE_VERSION_PATTERN.fullmatch(normalized):
        return f"{base}/releases/tag/v{normalized}"
    return f"{base}/releases/latest"


def build_about_info(
    root: Path,
    *,
    config_path: str | Path | None = None,
    frozen: bool = False,
    include_git: bool = False,
) -> dict[str, Any]:
    """Collect display-safe application metadata for the About dialog."""
    version = get_app_version(root, allow_git=include_git)
    return {
        "name": APP_GUI_NAME,
        "suite": APP_DISPLAY_NAME,
        "version": version,
        "commit": get_commit(root, allow_git=include_git),
        "python": sys.version.split()[0],
        "os": f"{platform.system()} {platform.release()} {platform.version()}",
        "mode": "Packaged" if frozen else "Source",
        "app_root": str(root),
        "config": str(config_path) if config_path else "",
        "license": APP_LICENSE,
        "repository": APP_REPOSITORY,
        "release_notes": release_notes_url(version),
    }
