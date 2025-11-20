"""
Config rendering helpers for Vein Manager.

This module takes care of building the config editor tabs, wiring search/filter
state, and keeping the search tab up to date so the main window can focus on
orchestration logic.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from PySide6 import QtWidgets

from .kvrow import KVRow
from .widgets import CollapsibleBox

if TYPE_CHECKING:  # pragma: no cover
    from Controller.vein_manager import Main


def _iter_keys_preserve(node: Any) -> Iterable:
    try:
        return list(node.keys())
    except Exception:
        return list(node) if isinstance(node, (list, tuple)) else []


def _human_title(key: str) -> str:
    return (key or "").replace("_", " ").strip().title() or "Top-level"


class ConfigRenderer:
    def __init__(self, owner: "Main"):
        self.owner = owner
        self._search_tab_idx: int | None = None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _humanize_label(value: str) -> str:
        import re

        normalized = (value or "").replace("_", " ").replace(".", "\u0007")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized.title()

    @staticmethod
    def _norm(text: str) -> str:
        import re

        return re.sub(r"[^a-z0-9]+", "", (text or "").lower())

    def _index_row(self, tab_name: str, row: KVRow) -> None:
        owner = self.owner
        if not hasattr(owner, "_search_index"):
            owner._search_index = {}

        label = row.label_text or ""
        path = row.path or ()
        dotted = ".".join(path)
        snake = "_".join(path)
        spaced = " ".join(path)

        section = None
        for (t, s), rows in owner._rows_in_section.items():
            if t == tab_name and row in rows:
                section = s
                break

        if isinstance(section, (tuple, list)):
            section_str = ".".join(section)
        else:
            section_str = section

        tab_path = ".".join([p for p in (tab_name, section_str) if p])

        raw_candidates = {
            label,
            dotted,
            snake,
            spaced,
            f"{tab_path}.{label}" if tab_path else label,
            f"{tab_path}.{dotted}" if tab_path else dotted,
        }
        toks = set()
        for candidate in raw_candidates:
            if candidate:
                toks.add(candidate.lower())
                toks.add(self._norm(candidate))
        owner._search_index[row] = toks

    def _add_scalar_row(
        self,
        tab_name: str,
        layout: QtWidgets.QVBoxLayout,
        path: Tuple[str, ...],
        value: Any,
        depth: int,
    ) -> None:
        owner = self.owner
        label = self._humanize_label(path[-1] if path else "")
        row = KVRow(label, path, value)
        row.changed.connect(owner._row_changed)

        if hasattr(row, "layout"):
            row.layout().setContentsMargins(12 * max(depth, 0), 0, 0, 0)

        layout.addWidget(row)

        owner.rows[path] = row
        owner._rows_by_tab[tab_name].append(row)

        parent_section = tuple(path[:-1])
        if (
            hasattr(owner, "_section_boxes")
            and (tab_name, parent_section) in owner._section_boxes
        ):
            owner._rows_in_section.setdefault((tab_name, parent_section), []).append(row)

        self._index_row(tab_name, row)

    def ensure_search_tab(self) -> str:
        owner = self.owner
        name = getattr(owner, "_search_tab_name", "Search")
        if name not in owner.tab_layouts:
            owner._add_tab(name)
        self._search_tab_idx = owner._tab_index(name)
        return name

    @staticmethod
    def _clear_layout(layout: QtWidgets.QLayout) -> None:
        while True:
            item = layout.takeAt(0)
            if not item:
                break
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild_search_tab(self, matches: List[KVRow]) -> None:
        owner = self.owner
        tab = self.ensure_search_tab()
        layout = owner.tab_layouts[tab]
        self._clear_layout(layout)

        grouped: Dict[str, Dict[str | None, List[KVRow]]] = {}
        for row in matches:
            path = row.path or ()
            top = path[0] if path else "_misc"
            section = (
                path[1]
                if len(path) >= 2
                and top.lower() not in ("top-level", "paths", "monitors")
                else None
            )
            grouped.setdefault(top, {}).setdefault(section, []).append(row)

        for top_key in sorted(grouped.keys(), key=str):
            top_box = CollapsibleBox(self._humanize_label(top_key))
            layout.addWidget(top_box)
            inner = top_box.layout_for_rows()

            for section_key in sorted(
                grouped[top_key].keys(), key=lambda x: (x is not None, str(x))
            ):
                rows = grouped[top_key][section_key]
                if section_key is None:
                    for row in rows:
                        clone = KVRow(row.label_text, row.path, row.value())
                        clone.changed.connect(owner._row_changed)
                        inner.addWidget(clone)
                else:
                    sub_box = CollapsibleBox(self._humanize_label(section_key))
                    inner.addWidget(sub_box)
                    sub_layout = sub_box.layout_for_rows()
                    for row in rows:
                        clone = KVRow(row.label_text, row.path, row.value())
                        clone.changed.connect(owner._row_changed)
                        sub_layout.addWidget(clone)

        layout.addStretch(1)

    def _remove_search_tab(self) -> None:
        owner = self.owner
        name = getattr(owner, "_search_tab_name", "Search")
        idx = owner._tab_index(name)
        if idx >= 0:
            owner.tabs.removeTab(idx)
        owner._tab_pages.pop(name, None)
        owner.tab_widgets.pop(name, None)
        owner.tab_layouts.pop(name, None)
        self._search_tab_idx = None
        owner._rebuild_base_titles()

    # ------------------------------------------------------------------ actions
    def build_tabs(self, data: Dict[str, Any]) -> None:
        owner = self.owner
        owner._sections_by_tab.clear()
        owner._rows_in_section.clear()
        owner._rows_by_tab.clear()
        owner.rows.clear()
        owner._search_index = {}
        owner._section_boxes = {}

        fixed = {getattr(owner, "_search_tab_name", "Search")}
        for i in reversed(range(owner.tabs.count())):
            base = owner._strip_cnt(owner.tabs.tabText(i))
            if base not in fixed:
                owner.tabs.removeTab(i)

        for name in list(owner.tab_layouts.keys()):
            vbox = owner.tab_layouts[name]
            while vbox.count():
                widget = vbox.takeAt(0).widget()
                if widget:
                    widget.deleteLater()
        owner.tab_widgets.clear()
        owner.tab_layouts.clear()

        owner._add_tab("Top-level")

        setattr(owner, "_cfg_version", None)
        if isinstance(data, dict) and "version" in data:
            owner._cfg_version = data.get("version")

        dict_tabs: List[Tuple[str, Dict[str, Any]]] = []
        for key in _iter_keys_preserve(data):
            if key == "version":
                continue
            value = data[key]
            if isinstance(value, dict):
                dict_tabs.append((key, value))
            else:
                self._add_scalar_row(
                    "Top-level",
                    owner.tab_layouts["Top-level"],
                    (str(key),),
                    value,
                    depth=0,
                )

        def render_into(
            tab_name: str,
            layout: QtWidgets.QVBoxLayout,
            prefix: Tuple[str, ...],
            node: Any,
            depth: int,
        ) -> None:
            if isinstance(node, dict):
                inner_layout = layout
                if depth > 0:
                    title = _human_title(prefix[-1])
                    box = CollapsibleBox(title)
                    layout.addWidget(box)
                    inner_layout = box.layout_for_rows()
                    owner._sections_by_tab.setdefault(tab_name, {})[prefix] = box
                    owner._section_boxes[(tab_name, prefix)] = box

                for child_key in _iter_keys_preserve(node):
                    render_into(
                        tab_name,
                        inner_layout,
                        prefix + (str(child_key),),
                        node[child_key],
                        depth + 1,
                    )
            else:
                val = node if not isinstance(node, list) else ", ".join(
                    str(x) for x in node
                )
                self._add_scalar_row(
                    tab_name, layout, prefix, val, depth=max(depth - 1, 0)
                )

        for key, node in dict_tabs:
            tab_name = _human_title(str(key))
            owner._add_tab(tab_name)
            render_into(
                tab_name,
                owner.tab_layouts[tab_name],
                (str(key),),
                node,
                depth=0,
            )
            owner.tab_layouts[tab_name].addStretch(1)

        owner.tab_layouts["Top-level"].addStretch(1)

        self.apply_filter(owner.filter.text())

    def apply_filter(self, text: str) -> None:
        owner = self.owner
        query = (text or "").strip()
        active = bool(query)

        def norm(value: str) -> str:
            value = value or ""
            value = value.replace("\u0007", ".").replace("_", ".")
            value = re.sub(r"\s+", ".", value)
            return value.lower()

        def base_of_tabtext(tab_text: str) -> str:
            return re.sub(r"\s+\(\d+\)$", "", tab_text or "")

        def set_tab_badge(tab_name: str, count: int, show_zero: bool) -> None:
            idx = owner._tab_index(tab_name)
            if idx >= 0:
                base = base_of_tabtext(owner.tabs.tabText(idx))
                owner.tabs.setTabText(
                    idx, base if (count <= 0 and not show_zero) else f"{base} ({count})"
                )

        if not active:
            for rows in owner._rows_by_tab.values():
                for row in rows:
                    row._match = True
                    row.setVisible(True)
            for i in range(owner.tabs.count()):
                base = base_of_tabtext(owner.tabs.tabText(i))
                owner.tabs.setTabText(i, base)
                try:
                    owner.tabs.setTabVisible(i, True)
                except Exception:
                    pass
            self._remove_search_tab()
            return

        normalized = norm(query)
        matches: List[KVRow] = []

        for tab_name, rows in owner._rows_by_tab.items():
            for row in rows:
                raw = ".".join(row.path)
                human = row.label_text or ""
                haystack = " ".join([human, raw])

                ok = normalized in norm(haystack)
                if not ok:
                    try:
                        ok = normalized in norm(str(row.value()))
                    except Exception:
                        ok = False

                row._match = bool(ok)
                row.setVisible(ok)
                if ok:
                    matches.append(row)

        for key, rows in owner._rows_in_section.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            tab_name, section = key
            match_count = sum(1 for row in rows if owner._row_matched(row))
            box = owner._sections_by_tab.get(tab_name, {}).get(section)
            if box:
                box.setVisible(match_count > 0)
                box.set_count(match_count, True)

        for tab_name, rows in owner._rows_by_tab.items():
            match_count = sum(1 for row in rows if owner._row_matched(row))
            set_tab_badge(tab_name, match_count, show_zero=True)

        for i in range(owner.tabs.count()):
            try:
                owner.tabs.setTabVisible(i, True)
            except Exception:
                pass

        search_tab = self.ensure_search_tab()
        self._rebuild_search_tab(matches)
        set_tab_badge(search_tab, len(matches), show_zero=True)

        if self._search_tab_idx is None:
            self._search_tab_idx = owner._tab_index(search_tab)
        if self._search_tab_idx is not None and self._search_tab_idx >= 0:
            owner.tabs.setCurrentIndex(self._search_tab_idx)
