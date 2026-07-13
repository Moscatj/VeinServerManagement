"""
Log panel helpers for Vein Manager.

This module owns the log side panel widgets, tailers, and background workers so
the main window can stay focused on orchestration.
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from Tools import log_events, log_search, mgmt_logs


class FileTail(QtCore.QObject):
    chunk = QtCore.Signal(str)

    def __init__(self, path_provider: callable, parent=None):
        """
        path_provider() -> Path
        Returns the *current* file to follow. May change over time.
        """
        super().__init__(parent)
        self._path_provider = path_provider
        self._file: Path | None = None
        self._pos = 0
        self._last_path: Path | None = None
        self._last_sig = (0, 0.0)  # (size, mtime)
        self.t = QtCore.QTimer(self)
        self.t.timeout.connect(self.poll)
        self.t.setInterval(300)

    def start(self):
        self._pos = 0
        self._open_current(end=True)
        self.t.start()

    def stop(self):
        self.t.stop()

    def _open_current(self, end: bool):
        p = self._path_provider()
        self._file = p if p and p.exists() else None
        self._pos = 0
        self._last_path = self._file
        self._last_sig = (0, 0.0)
        if not self._file:
            return
        try:
            with self._file.open("rb") as f:
                if end:
                    f.seek(0, 2)
                self._pos = f.tell()
                st = self._file.stat()
                self._last_sig = (st.st_size, st.st_mtime)
        except FileNotFoundError:
            self._file = None
            self._pos = 0
            self._last_path = None
            self._last_sig = (0, 0.0)

    def _rotated_or_truncated(self, path: Path, size: int, mtime: float) -> bool:
        if self._last_path != path:
            return True
        old_size, old_mtime = self._last_sig
        return size < old_size or (size == 0 and old_size > 0) or mtime < old_mtime

    def poll(self):
        if not self._path_provider:
            return
        p = self._path_provider()
        if not p:
            return
        try:
            st = p.stat()
            sig = (st.st_size, st.st_mtime)
        except FileNotFoundError:
            if self._file is not None:
                self._open_current(end=False)
            return
        if self._rotated_or_truncated(p, sig[0], sig[1]):
            self._open_current(end=False)
        if not self._file:
            return
        try:
            with self._file.open("rb") as f:
                f.seek(self._pos)
                chunk = f.read(16 * 1024)
                if not chunk:
                    self._last_sig = sig
                    return
                self._pos = f.tell()
                try:
                    st = self._file.stat()
                    self._last_sig = (st.st_size, st.st_mtime)
                except FileNotFoundError:
                    self._last_sig = sig
                self.chunk.emit(chunk.decode("utf-8", "replace"))
        except FileNotFoundError:
            self._open_current(end=False)


class LogSearchWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        ready = QtCore.Signal(list)
        error = QtCore.Signal(str)

    def __init__(
        self,
        *,
        subsystems: Optional[list[str]],
        pattern: str,
        since: Optional[str],
        limit: int,
        case_sensitive: bool,
        include_archive: bool,
        archive_only: Optional[set[str]] = None,
    ):
        super().__init__()
        self.subsystems = subsystems
        self.pattern = pattern
        self.since = since
        self.limit = limit
        self.case_sensitive = case_sensitive
        self.include_archive = include_archive
        self.archive_only = archive_only or set()
        self.signals = self.Signals()

    def run(self) -> None:
        try:
            since_ts = log_search.parse_since(self.since)
            hits = log_search.search_logs(
                subsystems=self.subsystems,
                pattern=self.pattern,
                case_sensitive=self.case_sensitive,
                since_ts=since_ts,
                max_hits=self.limit,
                include_archive=self.include_archive,
                archive_only=self.archive_only,
            )
            payload = [
                {
                    "subsystem": hit.subsystem,
                    "file": str(hit.file),
                    "line": hit.line_no,
                    "text": hit.text,
                }
                for hit in hits
            ]
            self.signals.ready.emit(payload)
        except Exception as exc:  # pragma: no cover - best-effort logging
            self.signals.error.emit(str(exc))


class LogErrorWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        ready = QtCore.Signal(list)
        error = QtCore.Signal(str)

    def __init__(
        self,
        *,
        subsystems: Optional[list[str]],
        since: Optional[str],
        limit: int,
        include_archive: bool = False,
        archive_only: bool = False,
    ):
        super().__init__()
        self.subsystems = subsystems
        self.since = since
        self.limit = limit
        self.include_archive = include_archive
        self.archive_only = archive_only
        self.signals = self.Signals()

    def run(self) -> None:
        try:
            subs = self.subsystems or mgmt_logs.available_subsystems()
            since_ts = log_search.parse_since(self.since)
            events = log_events.collect_recent_events(
                subsystems=subs,
                since_ts=since_ts,
                per_file_limit=20,
                max_events=self.limit,
                include_archive=self.include_archive,
                archive_only=self.archive_only,
            )
            payload = []
            root = mgmt_logs.management_log_root()
            for evt in events:
                try:
                    rel = evt.file.relative_to(root)
                    if len(rel.parts) >= 2:
                        subsystem = rel.parts[-2]
                    else:
                        subsystem = rel.parts[0]
                except Exception:
                    rel = evt.file
                    subsystem = "unknown"
                payload.append(
                    {
                        "subsystem": subsystem,
                        "file": str(rel),
                        "line": evt.line_no,
                        "level": evt.level,
                        "message": evt.message,
                        "timestamp": evt.timestamp,
                    }
                )
            self.signals.ready.emit(payload)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class ArchiveLogsWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        ready = QtCore.Signal(list)
        error = QtCore.Signal(str)

    def __init__(self, *, include_active: bool = False):
        super().__init__()
        self.include_active = include_active
        self.signals = self.Signals()

    def run(self) -> None:
        try:
            moved = mgmt_logs.archive_all_logs(include_active=self.include_active)
            self.signals.ready.emit(moved)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class LogPanelController(QtCore.QObject):
    """
    Encapsulates the log side-panel UI, tailers, and background workers.
    """

    def __init__(self, owner) -> None:
        super().__init__(owner)
        self.owner = owner
        self._pool = QtCore.QThreadPool.globalInstance()

        self._buf_game: list[str] = []
        self._buf_lm: list[str] = []
        self._buf_cm: list[str] = []

        self.tail_game: FileTail | None = None
        self.tail_lm: FileTail | None = None
        self.tail_cm: FileTail | None = None

        self._log_search_running = False
        self._error_refresh_running = False
        self._archiving_logs = False
        self._log_search_worker = None
        self._error_worker = None
        self._archive_worker = None

        self.flush_timer = QtCore.QTimer(self)
        self.flush_timer.setInterval(250)
        self.flush_timer.timeout.connect(self._flush_tail)

    # ------------------------------------------------------------------ wiring
    def connect_signals(self) -> None:
        o = self.owner
        o.b_clearlog.clicked.connect(self._clear_current_log)
        o.chk_live.toggled.connect(self.retail)
        o.btn_log_src_refresh.clicked.connect(self.populate_log_sources)
        o.btn_log_search.clicked.connect(self._run_log_search)
        o.btn_log_search_clear.clicked.connect(self._clear_log_search)
        o.cmb_mgmt_log_subsystem.currentIndexChanged.connect(
            lambda _: self._refresh_mgmt_log_files()
        )
        o.btn_mgmt_log_refresh.clicked.connect(self.populate_log_sources)
        o.btn_mgmt_log_load.clicked.connect(self._load_mgmt_log_file)
        o.btn_mgmt_log_open.clicked.connect(self._open_selected_mgmt_folder)
        o.btn_mgmt_archive.clicked.connect(self._archive_logs_now)
        o.cmb_mgmt_log_file.currentIndexChanged.connect(
            lambda _: self._load_mgmt_log_file(auto=True)
        )
        o.btn_error_refresh.clicked.connect(self._refresh_error_events)
        o.tbl_error_events.itemDoubleClicked.connect(self._open_error_log_from_table)

    def initialize(self) -> None:
        self.populate_log_sources()
        self.retail()
        self.flush_timer.start()

    # ----------------------------------------------------------------- tails
    def tail_stop_all(self):
        for t in (self.tail_game, self.tail_lm, self.tail_cm):
            try:
                if t:
                    t.stop()
                    t.deleteLater()
            except Exception:
                pass
        self.tail_game = self.tail_lm = self.tail_cm = None

    def retail(self):
        self.tail_stop_all()

        if not self.owner.chk_live.isChecked():
            self.owner._status("Live view disabled.")
            return

        def game_provider() -> Path:
            try:
                return self.owner._current_game_log_path()
            except Exception:
                return self.owner._resolved_paths()["log_file"]

        gp = game_provider()
        self.tail_game = FileTail(game_provider, parent=self)
        self.tail_game.chunk.connect(self._on_game_line)
        self.tail_game.start()
        if gp and gp.exists():
            self.owner._status(f"Tailing game: {gp}")
        else:
            self.owner._status(f"Waiting for game log to be created: {gp}")

        lm_provider = lambda: mgmt_logs.latest_log_path("monitor_log", "stdout")
        cm_provider = lambda: mgmt_logs.latest_log_path("crash_monitor", "stdout")

        self.tail_lm = FileTail(lm_provider, parent=self)
        self.tail_lm.chunk.connect(self._on_lm_line)
        self.tail_lm.start()

        self.tail_cm = FileTail(cm_provider, parent=self)
        self.tail_cm.chunk.connect(self._on_cm_line)
        self.tail_cm.start()

    @QtCore.Slot(str)
    def _on_game_line(self, s: str):
        self._buf_game.append(s)

    @QtCore.Slot(str)
    def _on_lm_line(self, s: str):
        self._buf_lm.append(s)

    @QtCore.Slot(str)
    def _on_cm_line(self, s: str):
        self._buf_cm.append(s)

    def _flush_tail(self):
        def cap(w: QtWidgets.QPlainTextEdit):
            if w.document().characterCount() > 500_000:
                w.clear()

        if not self.owner.chk_live.isChecked():
            for w in (self.owner.log_game, self.owner.log_lm, self.owner.log_cm):
                cap(w)
            return

        def flush_buf(buf: list[str], widget: QtWidgets.QPlainTextEdit):
            if not buf:
                return
            chunk = "".join(buf)
            buf.clear()
            cap(widget)
            widget.moveCursor(QtGui.QTextCursor.End)
            widget.insertPlainText(chunk)
            widget.moveCursor(QtGui.QTextCursor.End)

        flush_buf(self._buf_game, self.owner.log_game)
        flush_buf(self._buf_lm, self.owner.log_lm)
        flush_buf(self._buf_cm, self.owner.log_cm)

    # ---------------------------------------------------------------- log data
    def populate_log_sources(self):
        subsystems = mgmt_logs.available_subsystems(include_empty=True)
        self._set_subsystem_combo(self.owner.cmb_log_sources, subsystems, include_all=True)
        self._set_subsystem_combo(
            self.owner.cmb_mgmt_log_subsystem, subsystems, include_all=False
        )
        self._set_subsystem_combo(
            self.owner.cmb_error_subsystem, subsystems, include_all=True
        )
        if (
            self.owner.cmb_mgmt_log_subsystem
            and self.owner.cmb_mgmt_log_subsystem.currentData() in (None, "__none__")
            and self.owner.cmb_mgmt_log_subsystem.count() > 1
        ):
            self.owner.cmb_mgmt_log_subsystem.setCurrentIndex(1)
        self._refresh_mgmt_log_files()

    def _set_subsystem_combo(self, combo, subsystems, include_all: bool):
        if combo is None:
            return
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if combo is self.owner.cmb_mgmt_log_subsystem:
            combo.addItem("Select subsystem", "__none__")
        elif include_all:
            combo.addItem("All subsystems", "__all__")
        for name in subsystems:
            combo.addItem(name, name)
        combo.addItem("Archive (all subsystems)", "__archive__")
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _run_log_search(self):
        if self._log_search_running:
            return
        query = self.owner.ed_log_search.text().strip()
        if not query:
            self.owner.log_search_status.setText("Enter a search query to begin.")
            return
        subs_data = self.owner.cmb_log_sources.currentData()
        subsystems = None
        archive_only: set[str] = set()
        include_archive = self.owner.chk_log_include_archive.isChecked()
        if subs_data == "__archive__":
            subsystems = mgmt_logs.available_subsystems(include_empty=True)
            include_archive = True
            archive_only = set(subsystems)
        elif isinstance(subs_data, str) and subs_data not in (None, "__all__", ""):
            subsystems = [subs_data]
        limit = int(self.owner.spin_log_limit.value())
        since_expr = self.owner.cmb_log_since.currentData()
        case_sensitive = self.owner.chk_log_case.isChecked()
        self._log_search_running = True
        self.owner.btn_log_search.setEnabled(False)
        self.owner.log_search_status.setText("Searching.")
        worker = LogSearchWorker(
            subsystems=subsystems,
            pattern=query,
            since=since_expr,
            limit=limit,
            case_sensitive=case_sensitive,
            include_archive=include_archive,
            archive_only=archive_only,
        )
        worker.signals.ready.connect(self._log_search_ready)
        worker.signals.error.connect(self._log_search_error)
        self._pool.start(worker)
        self._log_search_worker = worker

    def _log_search_ready(self, payload: list[dict]):
        lines = [
            f"[{hit['subsystem']}] {hit['file']}:{hit['line']} {hit['text']}"
            for hit in payload
        ]
        text = "\n".join(lines) if lines else "No matches."
        self.owner.log_search_results.setPlainText(text)
        self.owner.log_search_status.setText(f"{len(payload)} match(es)")
        self.owner.btn_log_search.setEnabled(True)
        self._log_search_running = False
        self._log_search_worker = None

    def _log_search_error(self, message: str):
        self.owner.log_search_status.setText(f"Search failed: {message}")
        self.owner.btn_log_search.setEnabled(True)
        self._log_search_running = False
        self._log_search_worker = None

    def _clear_log_search(self):
        self.owner.log_search_results.clear()
        self.owner.log_search_status.setText("Idle")

    # ----------------------------- mgmt logs ---------------------------------
    def _refresh_mgmt_log_files(self):
        combo = getattr(self.owner, "cmb_mgmt_log_file", None)
        subs_combo = getattr(self.owner, "cmb_mgmt_log_subsystem", None)
        if not combo or not subs_combo:
            return
        subsystem_value = subs_combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        files: list[tuple[Path, str]] = []
        if subsystem_value == "__archive__":
            files = self._collect_archive_files()
        elif subsystem_value in (None, "__none__"):
            combo.blockSignals(False)
            self.owner.txt_mgmt_log.setPlainText("Select a subsystem to load logs.")
            return
        else:
            files = self._collect_subsystem_files(subsystem_value)
        for path, label in files:
            combo.addItem(label, str(path))
        combo.blockSignals(False)
        if files:
            combo.setCurrentIndex(0)
            self._load_mgmt_log_file(auto=True)
        else:
            self.owner.txt_mgmt_log.setPlainText("No logs found for this selection.")

    def _collect_subsystem_files(self, subsystem: str) -> list[tuple[Path, str]]:
        entries: list[tuple[Path, str]] = []
        seen: set[Path] = set()

        def _add(path: Path):
            nonlocal entries
            if path in seen or len(entries) >= 50:
                return
            seen.add(path)
            try:
                ts = path.stat().st_mtime
            except Exception:
                ts = 0.0
            prefix = "[Archive] " if mgmt_logs.is_archived_path(path) else ""
            label = f"{prefix}{path.name} ({self._format_timestamp(ts)})"
            entries.append((path, label))

        for path in mgmt_logs.iter_log_files(subsystem, include_archive=True):
            _add(path)

        live_root = mgmt_logs.subsystem_dir(subsystem)
        archive_root = mgmt_logs.ARCHIVE_ROOT / mgmt_logs._normalized_rel(
            mgmt_logs.LAYOUT.get(mgmt_logs._canon(subsystem)),
            mgmt_logs._canon(subsystem),
        )
        for root in (live_root, archive_root):
            try:
                for path in sorted(root.glob("**/*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
                    _add(path)
            except Exception:
                continue
        if len(entries) < 5:
            try:
                root = mgmt_logs.management_log_root()
                for path in sorted(root.glob("**/*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
                    name = path.name.lower()
                    parts = [p.lower() for p in path.parts]
                    if mgmt_logs._canon(subsystem) in name or mgmt_logs._canon(subsystem) in parts:
                        _add(path)
                        if len(entries) >= 50:
                            break
            except Exception:
                pass
        return entries[:50]

    def _collect_archive_files(self) -> list[tuple[Path, str]]:
        records: list[tuple[Path, float, str]] = []
        archive_root = mgmt_logs.ARCHIVE_ROOT
        try:
            globbed = sorted(archive_root.glob("**/*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            for path in globbed[:100]:
                try:
                    ts = path.stat().st_mtime
                except Exception:
                    ts = 0.0
                label = f"[Archive] {path.name} ({self._format_timestamp(ts)})"
                records.append((path, ts, label))
        except Exception:
            pass
        return [(path, label) for path, _, label in records[:50]]

    def _current_mgmt_log_file(self) -> Optional[Path]:
        combo = getattr(self.owner, "cmb_mgmt_log_file", None)
        if not combo:
            return None
        data = combo.currentData()
        if not data:
            return None
        return Path(data)

    def _load_mgmt_log_file(
        self,
        auto: bool = False,
        *,
        highlight_line: Optional[int] = None,
        highlight_level: Optional[str] = None,
    ):
        path = self._current_mgmt_log_file()
        if not path:
            if not auto:
                self.owner.txt_mgmt_log.setPlainText("No log file selected.")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.owner.txt_mgmt_log.setPlainText(text)
            if highlight_line:
                self._highlight_log_line(highlight_line, highlight_level)
            else:
                self.owner.txt_mgmt_log.setExtraSelections([])
        except Exception as exc:
            if not auto:
                self.owner.txt_mgmt_log.setPlainText(f"Failed to load log: {exc}")

    def _open_selected_mgmt_folder(self):
        path = self._current_mgmt_log_file()
        if path:
            self.owner._open_folder(path.parent)

    def _archive_logs_now(self):
        if self._archiving_logs:
            return
        self._archiving_logs = True
        self.owner.btn_mgmt_archive.setEnabled(False)
        self.owner._status("Archiving logs.")
        worker = ArchiveLogsWorker()
        worker.signals.ready.connect(self._archive_logs_done)
        worker.signals.error.connect(self._archive_logs_error)
        self._pool.start(worker)
        self._archive_worker = worker

    def _archive_logs_done(self, moved: list[tuple[Path, Path]]):
        self._archiving_logs = False
        self.owner.btn_mgmt_archive.setEnabled(True)
        self.populate_log_sources()
        count = len(moved)
        self.owner._status(f"Archived {count} log(s).")
        self._archive_worker = None

    def _archive_logs_error(self, message: str):
        self._archiving_logs = False
        self.owner.btn_mgmt_archive.setEnabled(True)
        self.owner._status(f"Archive failed: {message}")
        self._archive_worker = None

    def _refresh_error_events(self):
        if self._error_refresh_running:
            return
        subs_data = self.owner.cmb_error_subsystem.currentData()
        subsystems = None
        archive_only = False
        include_archive = self.owner.chk_error_include_archive.isChecked()
        if subs_data == "__archive__":
            subsystems = mgmt_logs.available_subsystems(include_empty=True)
            include_archive = True
            archive_only = True
        elif subs_data not in (None, "__all__", ""):
            subsystems = [subs_data]
        since_expr = self.owner.cmb_error_since.currentData()
        limit = int(self.owner.spin_error_limit.value())
        self._error_refresh_running = True
        self.owner.btn_error_refresh.setEnabled(False)
        self.owner.lbl_error_status.setText("Scanning errors.")
        worker = LogErrorWorker(
            subsystems=subsystems,
            since=since_expr,
            limit=limit,
            include_archive=include_archive,
            archive_only=archive_only,
        )
        worker.signals.ready.connect(self._error_ready)
        worker.signals.error.connect(self._error_error)
        self._pool.start(worker)
        self._error_worker = worker

    def _error_ready(self, payload: list[dict]):
        table = self.owner.tbl_error_events
        table.setRowCount(len(payload))
        latest_ts = 0.0
        for row, evt in enumerate(payload):
            ts = evt.get("timestamp", 0.0) or 0.0
            latest_ts = max(latest_ts, ts)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(evt["subsystem"]))
            ts_item = QtWidgets.QTableWidgetItem(self._format_timestamp(ts))
            ts_item.setData(QtCore.Qt.UserRole, ts)
            table.setItem(row, 1, ts_item)
            file_text = f"{evt['file']}:{evt['line']}"
            item_file = QtWidgets.QTableWidgetItem(file_text)
            item_file.setData(QtCore.Qt.UserRole, evt)
            table.setItem(row, 2, item_file)
            table.setItem(row, 3, QtWidgets.QTableWidgetItem(evt["level"]))
            table.setItem(row, 4, QtWidgets.QTableWidgetItem(evt["message"]))
        status = f"{len(payload)} event(s)"
        if latest_ts:
            status += f" - newest {self._format_timestamp(latest_ts)}"
        self.owner.lbl_error_status.setText(status)
        self.owner.btn_error_refresh.setEnabled(True)
        self._error_refresh_running = False
        self._error_worker = None

    def _error_error(self, message: str):
        self.owner.lbl_error_status.setText(f"Error summary failed: {message}")
        self.owner.btn_error_refresh.setEnabled(True)
        self._error_refresh_running = False
        self._error_worker = None

    def _open_error_log_from_table(self, item):
        row = item.row()
        data_item = self.owner.tbl_error_events.item(row, 2)
        if not data_item:
            return
        evt = data_item.data(QtCore.Qt.UserRole)
        if not isinstance(evt, dict):
            return
        rel_path = evt.get("file")
        line = int(evt.get("line", 1))
        subsystem = evt.get("subsystem", "")
        level = evt.get("level")
        self._load_log_into_subsystem_tab(
            rel_path, line, subsystem=subsystem, level=level
        )

    def _load_log_into_subsystem_tab(
        self, rel_path: str, line: int, *, subsystem: str, level: Optional[str]
    ):
        root = mgmt_logs.management_log_root()
        path = root / rel_path
        try:
            path = path.resolve()
        except Exception:
            pass
        archived = mgmt_logs.is_archived_path(path)
        subsystem = subsystem or self._infer_subsystem_from_path(path)
        self._ensure_subsystem_selected(subsystem, archived=archived)
        self._refresh_mgmt_log_files()
        combo = self.owner.cmb_mgmt_log_file
        idx = combo.findData(str(path))
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.owner.logTabs.setCurrentWidget(self.owner.mgmt_log_tab)
        self._load_mgmt_log_file(auto=True, highlight_line=line, highlight_level=level)

    # ---------------------------------------------------------------- helpers
    def _ensure_subsystem_selected(self, subsystem: str, archived: bool = False) -> None:
        combo = self.owner.cmb_mgmt_log_subsystem
        if not combo or not subsystem:
            return
        value = f"archive::{subsystem}" if archived else subsystem
        display = f"Archive: {subsystem}" if archived else subsystem
        idx = combo.findData(value)
        if idx < 0:
            combo.addItem(display, value)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _infer_subsystem_from_path(self, path: Path) -> str:
        root = mgmt_logs.management_log_root()
        try:
            rel = path.relative_to(root)
            parts = list(rel.parts)
            if parts and parts[0].lower() == "archive":
                return parts[1] if len(parts) > 1 else ""
            return parts[0] if parts else ""
        except Exception:
            return ""

    def _highlight_log_line(
        self, line_no: int, level: Optional[str] = None
    ) -> None:
        try:
            doc = self.owner.txt_mgmt_log.document()
            block = doc.findBlockByLineNumber(max(0, line_no - 1))
            if not block.isValid():
                return
            cursor = QtGui.QTextCursor(block)
            cursor.select(QtGui.QTextCursor.LineUnderCursor)

            selection_cursor = QtGui.QTextCursor(cursor)
            color = self._highlight_color_for_level(level)
            selection_cursor.setPosition(block.position())
            selection_cursor.setPosition(block.position() + block.length(), QtGui.QTextCursor.KeepAnchor)
            selection = QtWidgets.QTextEdit.ExtraSelection()
            selection.format.setBackground(QtGui.QColor(color))
            selection.cursor = selection_cursor
            self.owner.txt_mgmt_log.setExtraSelections([selection])
            self.owner.txt_mgmt_log.setTextCursor(selection_cursor)
            self.owner.txt_mgmt_log.ensureCursorVisible()
        except Exception:
            pass

    def _highlight_color_for_level(self, level: Optional[str]) -> str:
        if not level:
            return "#d0f0fd"
        lvl = level.upper()
        if lvl == "CRITICAL":
            return "#ffb3b3"
        if lvl == "ERROR":
            return "#ffd5b3"
        if lvl == "WARNING":
            return "#fffac0"
        return "#d0f0fd"

    def _format_timestamp(self, ts: float) -> str:
        if not ts:
            return "unknown"
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "unknown"

    def _clear_current_log(self):
        w = self.owner.logTabs.currentWidget()
        if isinstance(w, QtWidgets.QPlainTextEdit):
            w.clear()

    def _on_tail_cleanup(self):
        self.tail_stop_all()
        self.flush_timer.stop()
