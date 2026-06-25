"""
Status rendering adapter for Vein Manager.

The main window still owns the full status update logic; this adapter keeps the
controller boundary explicit while the GUI refactor continues.
"""

from __future__ import annotations

from typing import Dict


class StatusRenderer:
    def __init__(self, owner) -> None:
        self.owner = owner

    def apply(self, snap: Dict) -> None:
        self.owner._apply_status_snapshot_impl(snap)
