from __future__ import annotations

from pathlib import Path
from typing import Optional

from Tools import backups as _backups  # type: ignore

__all__ = ["make_backup", "prune_backups", "restore_from_latest"]


def make_backup(
    *,
    save_path: Optional[Path] = None,
    reason: str = "Manual",
    dst: Optional[Path] = None,
):
    return _backups.make_backup(reason=reason, files=None, dst=dst)


def prune_backups(path: Path) -> None:
    _backups.prune_backups(path=path)


def restore_from_latest(target_name: str) -> bool:
    return bool(_backups.restore_from_latest(target_name))
