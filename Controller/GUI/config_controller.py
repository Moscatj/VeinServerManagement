"""
Config controller helpers for Vein Manager.

This wraps common config interactions (filtering, tab badges, search tab) so the
main window can delegate to a smaller surface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .config_renderer import ConfigRenderer


class ConfigController:
    def __init__(self, owner) -> None:
        self.owner = owner
        self.renderer = ConfigRenderer(owner)

    def config_dir_path(self) -> Path:
        """Resolve the currently selected config directory."""
        try:
            entered = self.owner.ed_cfgdir.text().strip()
        except Exception:
            entered = ""
        base = entered or getattr(self.owner, "config_dir", "")
        return Path(base)

    def apply_filter(self, text: str) -> None:
        self.renderer.apply_filter(text)

    def build_tabs(self, data: Dict) -> None:
        self.renderer.build_tabs(data)

    def ensure_search_tab(self) -> str:
        return self.renderer.ensure_search_tab()

    def clear_filter(self) -> None:
        self.owner.filter.setText("")

    def cfg_selected(self, name: str) -> None:
        if not name:
            return
        cfg_dir = self.config_dir_path()
        self.owner.config_path = str(cfg_dir.joinpath(name))
        self.owner.load_config_text()
        self.owner.watch_config()
