# vein_manager.py — Vein Server Manager (clean header + Monitors tab + Advanced Overrides)
# Requires: PySide6; Windows is assumed for process checks and startfile
from __future__ import annotations
import json, os, sys, subprocess, time
from pathlib import Path
from typing import Any, Dict, Tuple, List
from datetime import datetime, timezone
from PySide6 import QtCore, QtGui, QtWidgets
from Tools.config_io import load_and_validate_config

# ----------------------------- Environment -----------------------------------
ENV = os.environ
ROOT = Path(ENV.get("VEIN_MGMT_ROOT", r"G:\Servers\VeinServer\ServerManagment"))
CONFIG_DIR = ROOT / "Config"
CTRL_DIR   = ROOT / "Controller"
RUNTIME_FALLBACK = ROOT / "Runtime"
PYEXE_ENV  = ENV.get("PYEXE", "")
APP_ORG = "RHG"
APP_NAME = "VeinManager"

def _pyexe() -> str:
    return PYEXE_ENV.strip() or ("py -3" if os.name == "nt" else sys.executable)

def first_json_in(folder: Path):
    try: return sorted(folder.glob("*.json"))[0]
    except IndexError: return None

DEFAULT_CONFIG = Path(ENV.get("VEIN_CONFIG") or (first_json_in(CONFIG_DIR) or CONFIG_DIR / "config.json"))

# ------------------------- Subprocess helpers --------------------------------
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def _hidden_kwargs():
    if os.name != "nt": return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return {"startupinfo": si, "creationflags": CREATE_NO_WINDOW}

def spawn(cmd: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.Popen:
    kw = {"shell": True, "cwd": str(cwd) if cwd else None}
    kw.update(_hidden_kwargs())
    if env is not None:
        kw["env"] = env
    return subprocess.Popen(cmd, **{k: v for k, v in kw.items() if v is not None})

def run_once(cmd: str, cwd: Path | None = None, timeout=60, env: dict | None = None):
    kw = {"shell": True, "cwd": str(cwd) if cwd else None,
          "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}
    kw.update(_hidden_kwargs())
    if env is not None:
        kw["env"] = env
    p = subprocess.Popen(cmd, **{k: v for k, v in kw.items() if v is not None})
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
    return p.returncode, out, err

def tasklist_running(image_name: str) -> bool:
    if os.name != "nt" or not image_name.strip(): return False
    name = image_name.strip().lower()
    try:
        kw = {"text": True}
        kw.update(_hidden_kwargs())
        out = subprocess.check_output(["tasklist"], **kw)
        for line in out.splitlines():
            if name in line.lower():
                return True
    except Exception:
        pass
    return False

def proc_exists_by_cmdline(substr: str) -> bool:
    """True if any process has 'substr' in CommandLine (Windows PowerShell)."""
    if os.name != "nt" or not substr:
        return False
    safe = substr.replace("'", "''")
    ps_cmd = (
        f"$s='{safe}'; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -ne $null -and $_.CommandLine -match "
        "[regex]::Escape($s) } | "
        "Select-Object -First 1 -Expand ProcessId"
    )
    cmd = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd]
    try:
        kw = {'text': True}
        kw.update(_hidden_kwargs())
        out = subprocess.check_output(cmd, **kw).strip()
        return bool(out)
    except Exception:
        return False

# --------------------------- Runtime helpers ---------------------------------
def _rt_paths(cfg_path: str) -> dict:
    from json import load
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = load(f)
    except Exception:
        cfg = {}
    rt = Path(cfg.get("runtime_dir") or (Path(__file__).parent.parent / "Runtime"))
    return {
        "rt": rt,
        "pid_crash": rt / "crash_monitor.pid",
        "pid_log": rt / "log_monitor.pid",
        "stop_crash": rt / "stop_crash_monitor.flag",
        "stop_log": rt / "stop_log_monitor.flag",
        "state_crash": rt / "crash_monitor_state.json",
        "state_log":   Path(cfg.get("monitor", {}).get("state_file") or (rt / "log_monitor_state.json")),
    }

def _file_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None

def _mkflag(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    try: p.write_text("", encoding="utf-8")
    except Exception: pass

def _rm(p: Path):
    try:
        if p.exists(): p.unlink()
    except Exception:
        pass

def _pid_alive(pid_str: str | None) -> bool:
    if not pid_str: return False
    try:
        pid = int(pid_str)
    except Exception:
        return False
    try:
        out = subprocess.check_output(["tasklist"], text=True, **_hidden_kwargs())
        return any(f" {pid} " in (" " + line + " ") for line in out.splitlines())
    except Exception:
        return False

def _wait_for_monitor_exit(pid_file: Path, timeout_sec: int = 30) -> bool:
    """Return True if monitor exited within timeout."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        pid = _file_text(pid_file)
        if not pid or not _pid_alive(pid):
            _rm(pid_file)
            return True
        time.sleep(0.5)
    return False

# ----------------------- Config helpers (paths, logs) -------------------------
def _load_cfg_for_runtime(cfg_path: str) -> dict:
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _runtime_paths(cfg_path: str) -> dict:
    cfg = _load_cfg_for_runtime(cfg_path)
    rt = Path(cfg.get("runtime_dir") or RUNTIME_FALLBACK)
    server_dir = Path(cfg.get("server_dir") or ROOT.parent)

    # Heartbeat seconds used by freshness window (prefer top-level; fallback to nested; else 60)
    hb_top = cfg.get("monitor_heartbeat_interval_seconds", None)
    hb_nested = (cfg.get("monitor", {}) or {}).get("heartbeat_interval_seconds", None)
    try:
        hb = int(hb_top if hb_top is not None else (hb_nested if hb_nested is not None else 60))
    except Exception:
        hb = 60

    monitor = cfg.get("monitor", {}) if isinstance(cfg.get("monitor", {}), dict) else {}

    return {
        "runtime_dir": rt,
        "state_flag": rt / "server_running.flag",
        "shutdown_flag": rt / "shutdown_in_progress.flag",
        "server_state": rt / "server_state.json",
        "crash_state": rt / "crash_monitor_state.json",
        "logs_dir": Path(cfg.get("logs_dir") or (server_dir / "Vein" / "Saved" / "Logs")),
        "absolute_log_file": Path(cfg.get("absolute_log_file")) if cfg.get("absolute_log_file") else None,
        "backup_root": Path(cfg.get("backup_root") or (ROOT / "Backups")),
        "features": cfg.get("features", {}),
        "log_monitor_enabled": bool(cfg.get("features", {}).get("enable_log_monitor", True)),
        "crash_monitor_enabled": bool(cfg.get("features", {}).get("enable_crash_monitor", True)),
        "hb_seconds": hb,
        "state_log": Path(monitor.get("state_file") or (rt / "log_monitor_state.json")),
    }


def _resolve_logfile(cfg_path: str, overrides: Dict[str, str]) -> Path:
    rp = _runtime_paths(cfg_path)
    if overrides.get("log_file"):
        return Path(overrides["log_file"])
    if rp["absolute_log_file"] and rp["absolute_log_file"].exists():
        return rp["absolute_log_file"]
    return rp["logs_dir"] / "Vein.log"

def _derived_scripts(cfg_path: str) -> Dict[str, Path]:
    base = CTRL_DIR
    return {
        "start_server": base / "start_server.py",
        "shutdown_server": base / "shutdown_server.py",
        "monitor_log": base / "monitor_log.py",
        "crash_monitor": base / "crash_monitor.py",
    }

def _resolved_paths(cfg_path: str, overrides: Dict[str, str]) -> Dict[str, Path]:
    d = _derived_scripts(cfg_path)
    res = {}
    for k, p in d.items():
        res[k] = Path(overrides.get(k, str(p)))
    res["log_file"] = _resolve_logfile(cfg_path, overrides)
    return res

def _file_exists(p: Path) -> bool:
    try: return p.exists()
    except Exception: return False

def _dot(on: bool, warn: bool=False) -> str:
    if warn:
        return "background:#EFB700; border-radius:6px; min-width:12px; min-height:12px;"
    return f"background:{'#2ECC71' if on else '#E74C3C'};border-radius:6px;min-width:12px;min-height:12px;"

def _age_str(iso_ts: str | None) -> str:
    if not iso_ts: return "—"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z",""))
        sec = max(0, int((datetime.utcnow() - dt).total_seconds()))
        if sec < 60: return f"{sec}s"
        if sec < 3600: return f"{sec//60}m {sec%60}s"
        return f"{sec//3600}h {(sec%3600)//60}m"
    except Exception:
        return "—"

# ----------------------------- Background poller ------------------------------
class StatusSnapshot(QtCore.QObject):
    ready = QtCore.Signal(dict)

class StatusPoller(QtCore.QRunnable):
    """
    Reads Runtime pid/flags and small JSONs off the UI thread and returns a compact snapshot:
      {'server':bool,'logmon':bool,'logmon_fresh':bool,'crashmon':bool,'crash_mode':str}
    """
    def __init__(self, cfg_path: str):
        super().__init__()
        self.setAutoDelete(True)
        self.cfg_path = cfg_path
        self.signals = StatusSnapshot()
        self._last_tasklist_at = 0.0
       
       #cache validated config + hb knobs once
        vcfg = load_and_validate_config(cfg_path)
        self.hb_seconds = vcfg.hb_seconds
        self.fresh_mult = vcfg.fresh_window_multiplier
        self.paths = {
            "server_dir": vcfg.server_dir,
            "runtime_dir": vcfg.runtime_dir,
            "logs_dir": vcfg.logs_dir,
            "save_dir": vcfg.save_dir,
        }
        self.selected_exe = vcfg.selected_exe  # if GUI needs to display/confirm

    # --- StatusPoller helpers --- 
    def _read_text(self, p: Path) -> str | None:
        try: return p.read_text(encoding="utf-8").strip()
        except Exception: return None

    def _read_json(self, p: Path) -> dict:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _pid_alive(self, pid_str: str | None) -> bool:
        if not pid_str:
            return False
        try:
            pid = int(pid_str)
        except Exception:
            return False
        try:
            # NOTE: CREATE_NO_WINDOW constant should already exist in your module
            out = subprocess.check_output(["tasklist"], text=True, creationflags=CREATE_NO_WINDOW)
            # naive but robust: look for the pid as a standalone token
            needle = f" {pid} "
            return any(needle in (" " + line + " ") for line in out.splitlines())
        except Exception:
            return False

    def _hb_knobs(self) -> tuple[int, float]:
        """Read heartbeat knobs from config.json; return (hb_seconds, fresh_mult)."""
        try:
            with open(self.cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            mon = cfg.get("monitor", {})
            hb = int(mon.get("heartbeat_seconds", 60))
            fresh_mult = float(mon.get("fresh_window_multiplier", 2.0))
            # bounds
            hb = max(5, hb)
            fresh_mult = 0.25 if fresh_mult < 0.25 else (10.0 if fresh_mult > 10.0 else fresh_mult)
            return hb, fresh_mult
        except Exception:
            return 60, 2.0

    def _is_fresh(self, state_path: Path, hb_seconds: int, mult: float) -> bool:
        """True if last_updated is within window; tolerant of bad/missing files."""
        try:
            data = self._read_json(state_path)
            lu = (data.get("last_updated") or "").strip()
            if not lu:
                return False
            # Make timezone-aware; ISO with 'Z' → '+00:00'
            from datetime import datetime, timezone
            lu_norm = lu.replace("Z", "+00:00")
            dt = datetime.fromisoformat(lu_norm)
            if dt.tzinfo is None:
                # assume UTC if writer forgot tz
                dt = dt.replace(tzinfo=timezone.utc)
            window = max(30, min(900, int(hb_seconds * mult)))
            age = (datetime.now(timezone.utc) - dt).total_seconds()
            return age <= window
        except Exception:
            return False

    def run(self):
        rp = _runtime_paths(self.cfg_path)
        rt = _rt_paths(self.cfg_path)

        # --- Heartbeat knobs used by both monitors and GUI freshness
        hb_seconds, fresh_mult = self._hb_knobs()

        # --- Server status: PID is truth source ---
        ss = self._read_json(rp["server_state"])
        pid_txt = str(ss.get("pid", "") or "").strip()
        if not pid_txt:
            # Fallback to shutdown/intent flag’s PID if present
            flag = self._read_json(rp["state_flag"])
            pid_txt = str(flag.get("pid", "") or "").strip()
        srv_on = self._pid_alive(pid_txt)

        # --- Log monitor ---
        lm_pid = self._read_text(rt["pid_log"])
        lm_on = self._pid_alive(lm_pid)
        lm_fresh = self._is_fresh(rt["state_log"], hb_seconds, fresh_mult)

        # --- Crash monitor ---
        cm_pid = self._read_text(rt["pid_crash"])
        cm_on = self._pid_alive(cm_pid)
        # Use the same state file namespace as runtime paths
        cs = self._read_json(rt["state_crash"])
        # Backward compatibility: support the older crash_state path if present
        if not cs:
            cs = self._read_json(rp.get("crash_state", rt["state_crash"]))
        mode = (cs.get("status") or cs.get("mode") or "unknown") if cs else "unknown"

        # Emit compact snapshot consumed by the UI
        self.signals.ready.emit({
            "server": bool(srv_on),
            "logmon": bool(lm_on),
            "logmon_fresh": bool(lm_fresh),
            "crashmon": bool(cm_on),
            "crash_mode": mode,  # "running" | "stopped" | "restart_pending" | "unknown"
        })

# --------------------------- Log tail (throttled) -----------------------------
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

    def _signature_changed(self) -> bool:
        if not self._file or not self._file.exists():
            return True
        try:
            st = self._file.stat()
            size, mt = st.st_size, st.st_mtime
            old_size, old_mt = self._last_sig
            # rotation/truncate: size dropped or mtime went backwards/changed with smaller size
            return (size < old_size) or (size == 0 and old_size > 0) or (mt != old_mt and size < old_size)
        except Exception:
            return True

    def poll(self):
        # If provider says the path changed, reopen.
        p = self._path_provider()
        if not p or not p.exists() or (self._file and str(p) != str(self._file)):
            self._open_current(end=False)

        if not self._file:
            return

        # Detect rotation/truncation
        if self._signature_changed():
            self._open_current(end=False)
            if not self._file:
                return

        try:
            with self._file.open("rb") as f:
                f.seek(self._pos)
                b = f.read(262144)
                if b:
                    self._pos = f.tell()
                    st = self._file.stat()
                    self._last_sig = (st.st_size, st.st_mtime)
                    self.chunk.emit(b.decode("utf-8", "replace"))
        except FileNotFoundError:
            self._open_current(end=False)


# ----------------------- JSON syntax highlight -------------------------------
class JsonHL(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.c = {}
    def highlightBlock(self, text):
        import re
        def f(hex): q = QtGui.QTextCharFormat(); q.setForeground(QtGui.QColor(hex)); return q
        self.c.setdefault("k", f("#7FB3D5"))
        self.c.setdefault("s", f("#ABEBC6"))
        self.c.setdefault("n", f("#F7DC6F"))
        self.c.setdefault("b", f("#F5B7B1"))
        self.c.setdefault("0", f("#D2B4DE"))
        for m in re.finditer(r'\"([^"]+)\"\s*(?=:\s)', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["k"])
        for m in re.finditer(r'\"([^\"\\]|\\.)*\"', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["s"])
        for m in re.finditer(r'(?<![\w\.])(-?\d+(\.\d+)?)', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["n"])
        for m in re.finditer(r'\b(true|false)\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["b"])
        for m in re.finditer(r'\bnull\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["0"])

# ------------------------------ Advanced Dialog -------------------------------
class AdvancedDialog(QtWidgets.QDialog):
    """Optional overrides. Defaults come from config, these persist in QSettings."""
    def __init__(self, cfg_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Overrides")
        self.setModal(True)
        self.resize(680, 360)
        self.cfg_path = cfg_path

        v = QtWidgets.QVBoxLayout(self)
        self.chk_use_defaults = QtWidgets.QCheckBox("Use defaults from config (ignore overrides)")
        v.addWidget(self.chk_use_defaults)

        grid = QtWidgets.QGridLayout(); v.addLayout(grid)
        labels = [
            ("Start Server (start_server.py)", "start_server"),
            ("Stop Server (shutdown_server.py)", "shutdown_server"),
            ("Log Monitor (monitor_log.py)", "monitor_log"),
            ("Crash Monitor (crash_monitor.py)", "crash_monitor"),
            ("Log file (override)", "log_file"),
        ]
        self.edits: Dict[str, QtWidgets.QLineEdit] = {}
        row = 0
        for text, key in labels:
            grid.addWidget(QtWidgets.QLabel(text), row, 0)
            le = QtWidgets.QLineEdit()
            btn = QtWidgets.QToolButton(); btn.setText("…")
            btn.clicked.connect(lambda _=None, k=key, e=le: self._pick(k, e))
            grid.addWidget(le, row, 1); grid.addWidget(btn, row, 2)
            self.edits[key] = le
            row += 1

        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save|QtWidgets.QDialogButtonBox.Cancel)
        reset = QtWidgets.QPushButton("Reset to Defaults")
        bb.addButton(reset, QtWidgets.QDialogButtonBox.ActionRole)
        v.addWidget(bb)

        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        reset.clicked.connect(self._reset_defaults)
        self.chk_use_defaults.toggled.connect(self._sync_enabled)

        self._load_settings()
        self._sync_enabled()

    def _pick(self, key: str, le: QtWidgets.QLineEdit):
        cur = le.text().strip() or str(Path.home())
        if key == "log_file":
            p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select log file", cur, "Log files (*.log *.txt);;All files (*.*)")
            if p: le.setText(p)
        else:
            p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select python script", cur, "Python (*.py);;All files (*.*)")
            if p: le.setText(p)

    def _reset_defaults(self):
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        q.remove("overrides")
        q.setValue("use_defaults", True)
        self._load_settings()
        self._sync_enabled()

    def _load_settings(self):
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        use_defs = bool(q.value("use_defaults", True))
        self.chk_use_defaults.setChecked(use_defs)
        ov = q.value("overrides", {}) or {}
        resolved = _resolved_paths(self.cfg_path, ov if not use_defs else {})
        for k, le in self.edits.items():
            le.setText(str(ov.get(k, "" if k=="log_file" else resolved.get(k,""))))

    def _sync_enabled(self):
        enabled = not self.chk_use_defaults.isChecked()
        for le in self.edits.values():
            le.setEnabled(enabled)

    def get_values(self) -> Dict[str, Any]:
        use_defs = self.chk_use_defaults.isChecked()
        ov = {}
        if not use_defs:
            for k, le in self.edits.items():
                val = le.text().strip()
                if val:
                    ov[k] = val
        return {"use_defaults": use_defs, "overrides": ov}

# ------------------------------ KV Row editor ---------------------------------
class KVRow(QtWidgets.QWidget):
    changed = QtCore.Signal(tuple, object)
    def __init__(self, label: str, path: Tuple[str, ...], value: Any, parent=None):
        super().__init__(parent)
        self.path = path
        self.label_text = label
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2); h.setSpacing(6)
        lab = QtWidgets.QLabel(label); lab.setMinimumWidth(180); h.addWidget(lab)
        if isinstance(value, bool):
            w = QtWidgets.QCheckBox(); w.setChecked(value)
            w.stateChanged.connect(lambda *_: self.changed.emit(self.path, bool(w.isChecked())))
            editor = w
        elif isinstance(value, int) and not isinstance(value, bool):
            w = QtWidgets.QLineEdit(str(value))
            w.setValidator(QtGui.QIntValidator(-2_147_483_648, 2_147_483_647))
            w.editingFinished.connect(lambda: self.changed.emit(self.path, int(w.text() or 0)))
            editor = w
        elif isinstance(value, float):
            w = QtWidgets.QLineEdit(str(value))
            w.setValidator(QtGui.QDoubleValidator(bottom=-1e308, top=1e308, decimals=12))
            w.editingFinished.connect(lambda: self.changed.emit(self.path, float(w.text() or 0.0)))
            editor = w
        else:
            box = QtWidgets.QWidget(); hb = QtWidgets.QHBoxLayout(box); hb.setContentsMargins(0,0,0,0)
            w = QtWidgets.QLineEdit("" if value is None else str(value)); hb.addWidget(w, 1)
            key = self.path[-1] if self.path else ""
            def looks_path_key(k: str) -> bool:
                k = k.lower(); return any(t in k for t in ("path", "file", "dir", "folder"))
            def is_dir_key(k: str) -> bool:
                k = k.lower(); return "dir" in k or "folder" in k
            if looks_path_key(key):
                btn = QtWidgets.QToolButton(); btn.setText("…"); btn.setToolTip("Browse")
                def pick():
                    cur = w.text().strip() or str(Path.home())
                    if is_dir_key(key):
                        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", cur)
                        if d: w.setText(d); self.changed.emit(self.path, d)
                    else:
                        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select file", cur, "All files (*.*)")
                        if p: w.setText(p); self.changed.emit(self.path, p)
                btn.clicked.connect(pick); hb.addWidget(btn, 0)
            w.editingFinished.connect(lambda: self.changed.emit(self.path, w.text()))
            editor = box
        editor.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        h.addWidget(editor)
        self.editor = editor

    def set_value(self, value: Any):
        if isinstance(self.editor, QtWidgets.QCheckBox):
            self.editor.blockSignals(True); self.editor.setChecked(bool(value)); self.editor.blockSignals(False)
        else:
            edits = self.editor.findChildren(QtWidgets.QLineEdit) or \
                    ([self.editor] if isinstance(self.editor, QtWidgets.QLineEdit) else [])
            if edits:
                e = edits[0]; e.blockSignals(True); e.setText("" if value is None else str(value)); e.blockSignals(False)

# ------------------------------ Main window ----------------------------------
class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vein Server Manager")
        self.resize(1380, 900)

        # basic state
        self.config_dir = str(CONFIG_DIR)
        self.config_path = str(DEFAULT_CONFIG)
        self.rows = {}
        self._saving = False

        # settings
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        self.use_defaults = bool(q.value("use_defaults", True))
        self.overrides = dict(q.value("overrides", {}) or {})

        # 1) build UI (creates tabs + self.chk_live, self.log_game/self.log_lm/self.log_cm)
        self._ui()

        # 2) signals
        self._signals()  # should connect: b_clearlog-> _clear_current_log, chk_live-> _retail

        # 3) init NEW 3-tab tail buffers/handles BEFORE tail_start()
        self._buf_game, self._buf_lm, self._buf_cm = [], [], []
        self.tail_game = None
        self.tail_lm   = None
        self.tail_cm   = None

        # one flush timer for all tails
        self.flush_timer = QtCore.QTimer(self)
        self.flush_timer.setInterval(250)
        self.flush_timer.timeout.connect(self._flush_tail)
        self.flush_timer.start()

        # 4) config load + JSON watches
        self.refresh_cfgs()
        self.load_json()
        self.watch_json()

        # 5) now it’s safe to start tailing
        self.tail_start()

        # 6) background status polling
        self._pool = QtCore.QThreadPool.globalInstance()
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._kick_status_poll)
        self._status_timer.start()

        self._restore_state()

    # ------------------------------- UI --------------------------------------
    def _ui(self):
        c = QtWidgets.QWidget(); self.setCentralWidget(c)
        v = QtWidgets.QVBoxLayout(c); v.setContentsMargins(8,8,8,8); v.setSpacing(10)

        # ---- Header panel ----
        header = QtWidgets.QWidget(); header.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        hv = QtWidgets.QVBoxLayout(header); hv.setContentsMargins(0,0,0,0); hv.setSpacing(8)

        g = QtWidgets.QGridLayout(); g.setContentsMargins(0,0,0,0); g.setHorizontalSpacing(8); g.setVerticalSpacing(6)
        g.setColumnStretch(0,0); g.setColumnStretch(1,1); g.setColumnStretch(2,0); hv.addLayout(g)

        r = 0
        self.ed_cfgdir = QtWidgets.QLineEdit(self.config_dir)
        self.b_cfgdir = QtWidgets.QPushButton("Browse Folder…"); self.b_cfgdir.setFixedWidth(130)
        self.b_reload_cfgs = QtWidgets.QPushButton("Refresh"); self.b_reload_cfgs.setFixedWidth(90)
        g.addWidget(QtWidgets.QLabel("Config Folder:"), r, 0)
        g.addWidget(self.ed_cfgdir, r, 1)
        g.addWidget(self.b_cfgdir, r, 2); r += 1

        self.cb_cfg = QtWidgets.QComboBox(); self.cb_cfg.setMinimumWidth(360)
        self.cb_cfg.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_cfg.setMinimumContentsLength(24)
        g.addWidget(QtWidgets.QLabel("Config File:"), r, 0)
        g.addWidget(self.cb_cfg, r, 1)
        g.addWidget(self.b_reload_cfgs, r, 2); r += 1

        # Shortcuts row (no path editors)
        short = QtWidgets.QHBoxLayout(); hv.addLayout(short)
        self.btn_logs = QtWidgets.QPushButton("Open Logs")
        self.btn_rt   = QtWidgets.QPushButton("Open Runtime")
        self.btn_bak  = QtWidgets.QPushButton("Open Backups")
        self.btn_ctl  = QtWidgets.QPushButton("Open Controller")
        self.btn_adv  = QtWidgets.QPushButton("Advanced…")
        short.addWidget(self.btn_logs); short.addWidget(self.btn_rt); short.addWidget(self.btn_bak)
        short.addWidget(self.btn_ctl);  short.addStretch(1); short.addWidget(self.btn_adv)

        # Actions + status lights
        act = QtWidgets.QHBoxLayout(); act.setContentsMargins(0,0,0,0); act.setSpacing(8); hv.addLayout(act)
        self.dot_srv = QtWidgets.QLabel(); self.dot_srv.setStyleSheet(_dot(False)); self.dot_srv.setFixedSize(14, 14)
        self.dot_lm  = QtWidgets.QLabel(); self.dot_lm.setStyleSheet(_dot(False));  self.dot_lm.setFixedSize(14, 14)
        self.dot_cm  = QtWidgets.QLabel(); self.dot_cm.setStyleSheet(_dot(False));  self.dot_cm.setFixedSize(14, 14)
        self.b_start   = QtWidgets.QPushButton("Start Server")
        self.b_stop    = QtWidgets.QPushButton("Stop Server")
        self.b_restart = QtWidgets.QPushButton("Restart")
        self.b_lm_on   = QtWidgets.QPushButton("Start Log Monitor")
        self.b_lm_off  = QtWidgets.QPushButton("Stop Log Monitor")
        self.b_cm_on   = QtWidgets.QPushButton("Start Crash Monitor")
        self.b_cm_off  = QtWidgets.QPushButton("Stop Crash Monitor")
        self.status    = QtWidgets.QLabel("Status: Idle")

        def add(label, dotw): act.addWidget(QtWidgets.QLabel(label)); act.addWidget(dotw); act.addSpacing(6)
        add("Server", self.dot_srv)
        act.addWidget(self.b_start); act.addWidget(self.b_stop); act.addWidget(self.b_restart); act.addSpacing(16)
        add("LogMon", self.dot_lm);  act.addWidget(self.b_lm_on); act.addWidget(self.b_lm_off); act.addSpacing(16)
        add("CrashMon", self.dot_cm);act.addWidget(self.b_cm_on); act.addWidget(self.b_cm_off); act.addStretch(1)
        act.addWidget(self.status)
        v.addWidget(header)

        # ---- Main splitter (tabs | json | log) ----
        main = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal); v.addWidget(main, 1)

        # LEFT: TABS
        left = QtWidgets.QWidget(); main.addWidget(left)
        lv = QtWidgets.QVBoxLayout(left); lv.setContentsMargins(0,0,0,0)

        topbar = QtWidgets.QHBoxLayout(); lv.addLayout(topbar)
        self.b_reload = QtWidgets.QPushButton("Reload JSON")
        self.b_validate = QtWidgets.QPushButton("Validate")
        self.b_save = QtWidgets.QPushButton("Save JSON (atomic)")
        self.filter = QtWidgets.QLineEdit(); self.filter.setPlaceholderText("Filter keys…")
        self.b_clearfilter = QtWidgets.QPushButton("Clear")
        topbar.addWidget(self.b_reload); topbar.addWidget(self.b_validate); topbar.addWidget(self.b_save); topbar.addStretch(1)
        topbar.addWidget(QtWidgets.QLabel("Filter:")); topbar.addWidget(self.filter, 1); topbar.addWidget(self.b_clearfilter)

        self.tabs = QtWidgets.QTabWidget(); lv.addWidget(self.tabs, 1)
        self.tab_widgets: Dict[str, QtWidgets.QWidget] = {}
        self.tab_layouts: Dict[str, QtWidgets.QVBoxLayout] = {}

        def add_tab(name: str):
            w = QtWidgets.QWidget()
            sv = QtWidgets.QVBoxLayout(w); sv.setContentsMargins(6,6,6,6); sv.setSpacing(6)
            scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
            container = QtWidgets.QWidget()
            vbox = QtWidgets.QVBoxLayout(container); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(6)
            scroll.setWidget(container)
            sv.addWidget(scroll, 1)
            self.tabs.addTab(w, name)
            self.tab_widgets[name] = container
            self.tab_layouts[name] = vbox

        for name in ["Paths","Server","Steam/Updates","Backups","Monitor (simple)","Monitor (advanced)","Features","Top-level"]:
            add_tab(name)

        # --- Monitors tab ---
        mon_tab = QtWidgets.QWidget()
        mon_v = QtWidgets.QVBoxLayout(mon_tab); mon_v.setContentsMargins(8,8,8,8); mon_v.setSpacing(8)

        # Log Monitor card
        logCard = QtWidgets.QGroupBox("Log Monitor"); logLay = QtWidgets.QGridLayout(logCard)
        self.lblLogDot = QtWidgets.QLabel(); self.lblLogDot.setFixedSize(14,14); self.lblLogDot.setStyleSheet(_dot(False))
        self.lblLogStatus = QtWidgets.QLabel("stopped")
        self.lblLogLast   = QtWidgets.QLabel("Last update: —")
        self.lblLogJoin   = QtWidgets.QLabel("Joinable: —")
        self.lblLogPlayers= QtWidgets.QLabel("Players: —")
        self.lblLogUptime = QtWidgets.QLabel("Uptime: —")
        logLay.addWidget(self.lblLogDot, 0,0)
        logLay.addWidget(self.lblLogStatus,0,1)
        logLay.addWidget(self.lblLogLast, 1,0,1,2)
        logLay.addWidget(self.lblLogJoin,  2,0,1,2)
        logLay.addWidget(self.lblLogPlayers,3,0,1,2)
        logLay.addWidget(self.lblLogUptime, 4,0,1,2)
        mon_v.addWidget(logCard)

        # Crash Monitor card
        crashCard = QtWidgets.QGroupBox("Crash Monitor"); cLay = QtWidgets.QGridLayout(crashCard)
        self.lblCrashDot  = QtWidgets.QLabel(); self.lblCrashDot.setFixedSize(14,14); self.lblCrashDot.setStyleSheet(_dot(False))
        self.lblCrashMode = QtWidgets.QLabel("stopped")
        self.lblCrashLast = QtWidgets.QLabel("Last heartbeat: —")
        cLay.addWidget(self.lblCrashDot, 0,0)
        cLay.addWidget(self.lblCrashMode,0,1)
        cLay.addWidget(self.lblCrashLast,1,0,1,2)
        mon_v.addWidget(crashCard)
        mon_v.addStretch(1)

        self.tabs.addTab(mon_tab, "Monitors")

        # JSON editor
        self.json = QtWidgets.QPlainTextEdit(); self.json.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.json.setFont(QtGui.QFont("Consolas", 10)); JsonHL(self.json.document())
        main.addWidget(self.json)

        # RIGHT: Logs with tabs
        right = QtWidgets.QWidget(); main.addWidget(right)
        rv = QtWidgets.QVBoxLayout(right); rv.setContentsMargins(0,0,0,0)

        cbar = QtWidgets.QHBoxLayout(); rv.addLayout(cbar)
        self.chk_live = QtWidgets.QCheckBox("Live (follow)"); self.chk_live.setChecked(True)
        self.b_clearlog = QtWidgets.QPushButton("Clear")
        cbar.addWidget(self.chk_live); cbar.addStretch(1); cbar.addWidget(self.b_clearlog)

        self.logTabs = QtWidgets.QTabWidget()
        self.log_game = QtWidgets.QPlainTextEdit(); self.log_game.setReadOnly(True); self.log_game.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.log_lm   = QtWidgets.QPlainTextEdit(); self.log_lm.setReadOnly(True);   self.log_lm.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.log_cm   = QtWidgets.QPlainTextEdit(); self.log_cm.setReadOnly(True);   self.log_cm.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.logTabs.addTab(self.log_game, "Game Log")
        self.logTabs.addTab(self.log_lm,   "Log Monitor")
        self.logTabs.addTab(self.log_cm,   "Crash Monitor")
        rv.addWidget(self.logTabs, 1)

        # compact state line under everything
        self.state_box = QtWidgets.QTextBrowser(); self.state_box.setMaximumHeight(120)
        v.addWidget(self.state_box)
        self.lbl_watch = QtWidgets.QLabel("Watching for external JSON changes…"); v.addWidget(self.lbl_watch)

    # ----------------------------- Signals ------------------------------------
    def _signals(self):
        self.b_cfgdir.clicked.connect(self.pick_cfg_dir)
        self.b_reload_cfgs.clicked.connect(self.refresh_cfgs)
        self.cb_cfg.currentTextChanged.connect(self._cfg_selected)

        self.b_reload.clicked.connect(self.load_json)
        self.b_save.clicked.connect(self.save_atomic)
        self.b_validate.clicked.connect(self.validate_json)
        self.filter.textChanged.connect(self._apply_filter)
        self.b_clearfilter.clicked.connect(lambda: self.filter.setText(""))
        self.b_clearlog.clicked.connect(self._clear_current_log)
        self.chk_live.toggled.connect(self._retail)


        self.btn_logs.clicked.connect(lambda: self._open_folder(self._resolved_paths()["log_file"].parent))
        self.btn_rt.clicked.connect(lambda: self._open_folder(_runtime_paths(self.config_path)["runtime_dir"]))
        self.btn_bak.clicked.connect(lambda: self._open_folder(_runtime_paths(self.config_path)["backup_root"]))
        self.btn_ctl.clicked.connect(lambda: self._open_folder(CTRL_DIR))
        self.btn_adv.clicked.connect(self._open_advanced)

        self.b_start.clicked.connect(self.start_server)
        self.b_stop.clicked.connect(self.stop_server)
        self.b_restart.clicked.connect(self.restart_server)
        self.b_lm_on.clicked.connect(self.start_lm)
        self.b_lm_off.clicked.connect(self.stop_lm)
        self.b_cm_on.clicked.connect(self.start_cm)
        self.b_cm_off.clicked.connect(self.stop_cm)

    # -------------------------- Config folder ---------------------------------
    def pick_cfg_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Config Folder", self.ed_cfgdir.text().strip() or str(CONFIG_DIR))
        if d:
            self.ed_cfgdir.setText(d)
            self.config_dir = d
            self.refresh_cfgs()

    def refresh_cfgs(self):
        folder = Path(self.ed_cfgdir.text().strip() or self.config_dir)
        self.cb_cfg.blockSignals(True); self.cb_cfg.clear()
        if folder.exists():
            files = sorted([p.name for p in folder.glob("*.json")])
            self.cb_cfg.addItems(files)
            if files:
                cur = Path(self.config_path).name if self.config_path else ""
                self.cb_cfg.setCurrentText(cur if cur in files else files[0])
        self.cb_cfg.blockSignals(False)
        self._cfg_selected(self.cb_cfg.currentText())

    def _cfg_selected(self, name: str):
        if not name: return
        self.config_path = str(Path(self.ed_cfgdir.text().strip()).joinpath(name))
        self.load_json()
        self.watch_json()

    # ------------------------------- JSON IO ----------------------------------
    def load_json(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except Exception as e:
            self._status(f"Load error: {e}")
            return
        self._data = data
        self.json.blockSignals(True)
        self.json.setPlainText(json.dumps(data, indent=2))
        self.json.blockSignals(False)
        self._build_tabs(data)
        self._status("Loaded JSON.")

    def _build_tabs(self, data: dict):
        for vbox in self.tab_layouts.values():
            while vbox.count():
                w = vbox.takeAt(0).widget()
                if w: w.deleteLater()
        self.rows.clear()
        def add(tab: str, key: str, path: Tuple[str, ...], val: Any):
            row = KVRow(key, path, val); row.changed.connect(self._row_changed)
            self.tab_layouts[tab].addWidget(row); self.rows[path] = row

        # Paths
        for k in ["server_dir","save_dir","logs_dir","absolute_log_file","backup_root","map_path","runtime_dir"]:
            if k in data: add("Paths", k, (k,), data[k])
        # Server
        for k in ["server_output_mode","multi_home_ip","game_port","query_port","enable_query_port",
                  "extra_launch_args","max_players","show_monitor_window","headless_mode"]:
            if k in data: add("Server", k, (k,), data[k])
        # Steam/Updates
        for k in ["steamcmd_path","app_id","auto_update_on_start","steam_update_validate","steam_update_beta",
                  "steam_update_beta_password","steam_update_retries","steam_update_timeout_seconds"]:
            if k in data: add("Steam/Updates", k, (k,), data[k])
        # Backups
        for k in ["max_backups","backup_max_age_days","backup_folders","nightly_backup"]:
            if k in data: add("Backups", k, (k,), data[k])
        # Monitor (simple flat fields)
        for k in ["monitor_heartbeat_interval_seconds","monitor_log_wait_timeout_seconds","crash_monitor_interval_seconds",
                  "crash_monitor_idle_notify_minutes","log_rotation_retries","log_rotation_retry_sleep_seconds",
                  "preboot_shutdown","backup_on_detect","shutdown_timeout_sec","pre_shutdown_warning_seconds",
                  "stale_flag_delay_sec","restart_throttle_seconds","startup_quiet_seconds","crash_snippet_lines",
                  "logout_backup_debounce_seconds","autosave_backup_cooldown_seconds","kill_ue_helpers_on_shutdown"]:
            if k in data: add("Monitor (simple)", k, (k,), data[k])
        # Monitor (advanced nested)
        mon = data.get("monitor", {})
        if isinstance(mon, dict):
            for k in ["enable","heartbeat_interval_seconds","state_file","wait_for_server_start_seconds",
                      "wait_for_log_appearance_seconds","tail_poll_interval_ms"]:
                if k in mon: add("Monitor (advanced)", f"monitor.{k}", ("monitor",k), mon[k])
            for sub in ["track","notify","backups"]:
                sd = mon.get(sub, {})
                if isinstance(sd, dict):
                    for k,v in sd.items():
                        add("Monitor (advanced)", f"monitor.{sub}.{k}", ("monitor",sub,k), v)
        # Features
        feats = data.get("features", {})
        if isinstance(feats, dict):
            for k,v in feats.items():
                add("Features", f"features.{k}", ("features",k), v)
        # Top-level scalars not covered
        skip = {"features","monitor","server_dir","save_dir","logs_dir","absolute_log_file","backup_root","map_path","runtime_dir",
                "server_output_mode","multi_home_ip","game_port","query_port","enable_query_port","extra_launch_args",
                "max_players","show_monitor_window","headless_mode","steamcmd_path","app_id","auto_update_on_start","steam_update_validate",
                "steam_update_beta","steam_update_beta_password","steam_update_retries","steam_update_timeout_seconds",
                "max_backups","backup_max_age_days","backup_folders","nightly_backup",
                "monitor_heartbeat_interval_seconds","monitor_log_wait_timeout_seconds","crash_monitor_interval_seconds",
                "crash_monitor_idle_notify_minutes","log_rotation_retries","log_rotation_retry_sleep_seconds","preboot_shutdown",
                "backup_on_detect","shutdown_timeout_sec","pre_shutdown_warning_seconds","stale_flag_delay_sec",
                "restart_throttle_seconds","startup_quiet_seconds","crash_snippet_lines","logout_backup_debounce_seconds",
                "autosave_backup_cooldown_seconds","kill_ue_helpers_on_shutdown"}
        for k,v in data.items():
            if k in skip: continue
            if isinstance(v,(bool,int,float,str)):
                add("Top-level", k, (k,), v)
        for vbox in self.tab_layouts.values(): vbox.addStretch(1)
        self._apply_filter(self.filter.text())

    def _row_changed(self, path: Tuple[str, ...], val: Any):
        data = self._data; cur = data
        for p in path[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[path[-1]] = val
        self._data = data
        self.json.blockSignals(True)
        self.json.setPlainText(json.dumps(data, indent=2))
        self.json.blockSignals(False)

    def validate_json(self):
        try:
            json.loads(self.json.toPlainText())
            self._status("JSON parses ✅")
        except Exception as e:
            self._status(f"JSON parse error: {e}")

    def save_atomic(self):
        try:
            path = Path(self.config_path)
            tmp = path.with_suffix(path.suffix + ".tmp")
            self._saving = True
            with tmp.open("w", encoding="utf-8") as f:
                f.write(self.json.toPlainText())
            os.replace(tmp, path)
            self._status("Saved JSON atomically.")
        except Exception as e:
            self._status(f"Save failed: {e}")
        finally:
            QtCore.QTimer.singleShot(250, lambda: setattr(self, "_saving", False))

    # ---------------------------- Watch / tail --------------------------------
    def watch_json(self):
        try:
            if hasattr(self, "watcher"):
                for p in self.watcher.files():
                    try: self.watcher.removePath(p)
                    except Exception: pass
            self.watcher = QtCore.QFileSystemWatcher(self)
            if Path(self.config_path).exists():
                self.watcher.addPath(self.config_path)
            self.watcher.fileChanged.connect(lambda _:
                (self._saving and None) or QtCore.QTimer.singleShot(300, self.load_json))
        except Exception:
            pass

    def _clear_current_log(self):
        w = self.logTabs.currentWidget()
        if isinstance(w, QtWidgets.QPlainTextEdit):
            w.clear()
    
    def _current_game_log_path(self) -> Path:
        # Prefer the monitor’s notion of the active file if available
        rt = _rt_paths(self.config_path)
        lms = self._safe_json(rt["state_log"])
        if lms and lms.get("tailing_file"):
            try:
                p = Path(lms["tailing_file"])
                if p.exists():
                    return p
            except Exception:
                pass
        # Fallback to resolved default (absolute_log_file or Logs/Vein.log)
        return self._resolved_paths()["log_file"]

    def tail_start(self):
        self._retail()

    def _tail_stop_all(self):
        for t in (self.tail_game, self.tail_lm, self.tail_cm):
            try:
                if t:
                    t.stop()
                    t.deleteLater()
            except Exception:
                pass
        self.tail_game = self.tail_lm = self.tail_cm = None

    def _retail(self):
        self._tail_stop_all()

        if not self.chk_live.isChecked():
            self._status("Live view disabled.")
            return

        # Provider that re-evaluates the active game log path dynamically
        def game_provider() -> Path:
            try:
                return self._current_game_log_path()
            except Exception:
                return self._resolved_paths()["log_file"]

        # Game log (rotation-aware)
        gp = game_provider()
        if gp and gp.exists():
            self.tail_game = FileTail(game_provider)
            self.tail_game.chunk.connect(self._on_game_line)
            self.tail_game.start()
            self._status(f"Tailing game: {gp}")
        else:
            self._status(f"Game log not found: {gp}")

        # Management logs (stdout files) – unchanged
        cfg = _load_cfg_for_runtime(self.config_path)
        mgmt_log_dir = Path(cfg.get("mgmt_log_dir", ROOT / "Logs"))
        lm_file = mgmt_log_dir / "monitor_log.stdout.log"
        cm_file = mgmt_log_dir / "crash_monitor.stdout.log"

        if lm_file.exists():
            self.tail_lm = FileTail(lambda: lm_file)
            self.tail_lm.chunk.connect(self._on_lm_line)
            self.tail_lm.start()
        if cm_file.exists():
            self.tail_cm = FileTail(lambda: cm_file)
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
        # keep logs from growing unbounded even when paused
        def cap(w: QtWidgets.QPlainTextEdit):
            if w.document().characterCount() > 500_000:
                w.clear()

        if not self.chk_live.isChecked():
            for w in (self.log_game, self.log_lm, self.log_cm):
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

        flush_buf(self._buf_game, self.log_game)
        flush_buf(self._buf_lm,   self.log_lm)
        flush_buf(self._buf_cm,   self.log_cm)


    # ------------------------ Server / monitors -------------------------------
    def _resolved_paths(self) -> Dict[str, Path]:
        ov = {} if self.use_defaults else self.overrides
        return _resolved_paths(self.config_path, ov)

    def start_server(self):
        paths = self._resolved_paths()
        py = paths["start_server"]
        if not py.exists():
            self._status("start_server.py not found."); return
        env = os.environ.copy(); env["VEIN_CONFIG"] = self.config_path
        try:
            spawn(f'{_pyexe()} "{py}"', py.parent, env=env)
            self._status("Server starting…")
        except Exception as e:
            self._status(f"Start failed: {e}")

    def stop_server(self):
        paths = self._resolved_paths()
        py = paths["shutdown_server"]
        if not py.exists():
            self._status("shutdown_server.py not found."); return
        try:
            code, out, err = run_once(f'{_pyexe()} "{py}"', cwd=py.parent, timeout=180)
            self._status("Server stop requested." if code == 0 else f"Stop returned {code}. {err or out}")
        except Exception as e:
            self._status(f"Stop failed: {e}")

    def restart_server(self):
        self.stop_server()
        QtCore.QTimer.singleShot(1200, self.start_server)

    def start_lm(self):
        paths = self._resolved_paths()
        mon_py = paths["monitor_log"]
        if not mon_py.exists():
            self._status("monitor_log.py not found."); return
        rp = _rt_paths(self.config_path)
        _rm(rp["stop_log"]); _rm(rp["pid_log"])
        env = os.environ.copy(); env["VEIN_CONFIG"] = self.config_path
        spawn(f'{_pyexe()} "{mon_py}" --follow', mon_py.parent, env=env)
        self._status("Log monitor starting…")
        if _runtime_paths(self.config_path)["log_monitor_enabled"]:
            self.chk_live.setChecked(True)

    def stop_lm(self):
        rp = _rt_paths(self.config_path)
        _mkflag(rp["stop_log"])
        self._status("Stopping Log Monitor…")
        if _wait_for_monitor_exit(rp["pid_log"], timeout_sec=20):
            self._status("Log Monitor stopped.")
        else:
            # gentle Python fallback (existing utils hook)
            try:
                run_once(
                    f'{_pyexe()} -c "import sys;sys.path.insert(0, r\'{CTRL_DIR}\');import utils;utils.stop_log_monitor();print(\'OK\')"',
                    CTRL_DIR, timeout=10
                )
            except Exception:
                pass
            if not _wait_for_monitor_exit(rp["pid_log"], timeout_sec=10):
                # last resort: force-kill by command line match
                try:
                    run_once('powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | '
                             'Where-Object { $_.CommandLine -match \'monitor_log.py\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
                             timeout=8)
                except Exception:
                    pass
            self._status("Log Monitor stop requested.")

    def start_cm(self):
        paths = self._resolved_paths()
        cm_py = paths["crash_monitor"]
        if not cm_py.exists():
            self._status("crash_monitor.py not found."); return
        rp = _rt_paths(self.config_path)
        _rm(rp["stop_crash"]); _rm(rp["pid_crash"])
        env = os.environ.copy(); env["VEIN_CONFIG"] = self.config_path
        spawn(f'{_pyexe()} "{cm_py}"', cm_py.parent, env=env)
        self._status("Crash monitor starting…")

    def stop_cm(self):
        rp = _rt_paths(self.config_path)
        _mkflag(rp["stop_crash"])
        self._status("Stopping Crash Monitor…")
        if _wait_for_monitor_exit(rp["pid_crash"], timeout_sec=30):
            self._status("Crash Monitor stopped.")
        else:
            try:
                run_once(
                    f'{_pyexe()} -c "import sys;sys.path.insert(0, r\'{CTRL_DIR}\');import utils;utils.stop_crash_monitor();print(\'OK\')"',
                    CTRL_DIR, timeout=10
                )
            except Exception:
                pass
            if not _wait_for_monitor_exit(rp["pid_crash"], timeout_sec=10):
                try:
                    run_once('powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | '
                             'Where-Object { $_.CommandLine -match \'crash_monitor.py\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
                             timeout=8)
                except Exception:
                    pass
            self._status("Crash Monitor stop requested.")

    # ----------------------- Background status wiring -------------------------
    def _kick_status_poll(self):
        worker = StatusPoller(self.config_path)
        worker.signals.ready.connect(self._apply_status_snapshot)
        self._pool.start(worker)

    def _apply_status_snapshot(self, snap: dict):
        # Update gumballs without blocking
        def dot(on, warn=False):
            return _dot(on, warn)
        # Server
        self.dot_srv.setStyleSheet(dot(snap.get("server", False)))
        # Log monitor: green if alive+fresh; yellow if alive but stale
        lm_on = snap.get("logmon", False)
        lm_fresh = snap.get("logmon_fresh", False)
        self.dot_lm.setStyleSheet(dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh)))
        # Crash monitor
        cm_on = snap.get("crashmon", False)
        self.dot_cm.setStyleSheet(dot(cm_on))
        cmode = snap.get("crash_mode", "unknown")
        self.lblCrashMode.setText(cmode)
        self.b_cm_on.setToolTip(f"Crash monitor mode: {cmode}")
        self.b_cm_off.setToolTip(f"Crash monitor mode: {cmode}")

        # Monitors tab detail (read server_state only once here)
        rp = _runtime_paths(self.config_path)
        rt = _rt_paths(self.config_path)
        st = self._safe_json(rp["server_state"])
        lms = self._safe_json(rt["state_log"])
        last = (lms.get("last_updated") if lms else None)
        self.lblLogDot.setStyleSheet(dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh)))
        self.lblLogStatus.setText("running" if lm_on else "stopped")
        self.lblLogLast.setText(f"Last update: {_age_str(last)}")
        self.lblLogJoin.setText(f"Joinable: {st.get('server_joinable') if st else '—'}")
        self.lblLogPlayers.setText(f"Players: {st.get('player_count') if st else '—'}")
        if st and isinstance(st.get("uptime_seconds"), int):
            up = st["uptime_seconds"]; self.lblLogUptime.setText(f"Uptime: {up//3600:02d}:{(up%3600)//60:02d}:{up%60:02d}")
        else:
            self.lblLogUptime.setText("Uptime: —")

        # Hint the tailer in case path switched (next poll will re-open)
        if self.tail_game:
            try:
                _ = self._current_game_log_path()  # will be read by provider on next poll
            except Exception:
                pass

        cs = self._safe_json(rp["crash_state"])
        self.lblCrashDot.setStyleSheet(dot(cm_on))
        self.lblCrashLast.setText(f"Last heartbeat: {_age_str(cs.get('ts'))}")

        # Compact state line (fallback info)
        self.state_box.setText(
            f"Server flag: {'present' if _file_exists(rp['state_flag']) else 'absent'}   |   "
            f"Shutdown flag: {'present' if _file_exists(rp['shutdown_flag']) else 'absent'}"
        )
        
                # Auto-(re)start log monitor if:
        #   - server is running,
        #   - log monitor feature is enabled in config,
        #   - and monitor isn't running or marked fresh
        if not hasattr(self, "_lm_autostart_last"):
            self._lm_autostart_last = 0.0
        try:
            server_on = bool(snap.get("server", False))
            lm_on = bool(snap.get("logmon", False))
            lm_fresh = bool(snap.get("logmon_fresh", False))
            now = time.time()

            cfg = _load_cfg_for_runtime(self.config_path)
            features = cfg.get("features", {})
            logmon_enabled = features.get("enable_log_monitor", True)

            # also check if a manual stop flag exists to respect user intent
            rt = _rt_paths(self.config_path)
            manual_stop = rt["stop_log"].exists() if "stop_log" in rt else False

            if (
                server_on
                and logmon_enabled
                and not lm_on
                and not manual_stop
                and (now - self._lm_autostart_last) > 5.0
            ):
                self._lm_autostart_last = now
                self.start_lm()
        except Exception:
            pass


    # ------------------------------- Misc -------------------------------------
    def _safe_json(self, p: Path) -> dict:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _apply_filter(self, t: str):
        t = (t or "").strip().lower()
        for row in self.rows.values():
            row.setVisible((t in row.label_text.lower()) if t else True)

    def _status(self, s: str): self.status.setText(f"Status: {s}")

    def _open_folder(self, p: Path):
        if not p: return
        try:
            os.startfile(str(p))  # Windows
        except Exception:
            pass

    def _open_advanced(self):
        dlg = AdvancedDialog(self.config_path, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            vals = dlg.get_values()
            self.use_defaults = bool(vals.get("use_defaults", True))
            self.overrides = dict(vals.get("overrides", {}))
            q = QtCore.QSettings(APP_ORG, APP_NAME)
            q.setValue("use_defaults", self.use_defaults)
            q.setValue("overrides", self.overrides)
            self._retail()
            self._status("Overrides updated.")

    def _restore_state(self):
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        g = q.value("main/geometry"); st = q.value("main/state")
        if g: self.restoreGeometry(g)
        if st: self.restoreState(st)

    def closeEvent(self, e: QtGui.QCloseEvent):
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        q.setValue("main/geometry", self.saveGeometry())
        q.setValue("main/state", self.saveState())
        e.accept()

# --------------------------------- main --------------------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    if os.name == "nt":
        app.setStyle("Fusion")
    w = Main(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
