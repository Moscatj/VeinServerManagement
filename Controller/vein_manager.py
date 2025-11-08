# vein_manager.py — Vein Server Manager (clean header + Monitors tab + Advanced Overrides)
from __future__ import annotations

# --- stdlib imports first
import json, os, sys, subprocess, time, re
from pathlib import Path
from typing import Any, Dict, Tuple, List
from datetime import datetime, timezone
import collections
# --- Qt
from PySide6 import QtCore, QtGui, QtWidgets

# ----------------------------- Environment -----------------------------------
ENV = os.environ
ROOT = Path(ENV.get("VEIN_MGMT_ROOT", r"G:\Servers\VeinServer\VeinServerManagement"))
CONFIG_DIR = ROOT / "Config"
CTRL_DIR   = ROOT / "Controller"
RUNTIME_FALLBACK = ROOT / "Runtime"
PYEXE_ENV  = ENV.get("PYEXE", "")
APP_ORG = "RHG"
APP_NAME = "VeinManager"
LOGS_DIR = ROOT / "Logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure we can import Tools/* even if PYTHONPATH wasn't set by the .bat
if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))

# Now it is safe to import Tools modules
try:
    from Tools.config_io import load_and_validate_config
except Exception as e:
    print(f"[FATAL] Could not import Tools.config_io from {CTRL_DIR}: {e}")
    sys.exit(1)

def _pyexe() -> str:
    return PYEXE_ENV.strip() or ("py -3" if os.name == "nt" else sys.executable)

# --- move these helpers ABOVE DEFAULT_CONFIG ---
def _is_yaml_path(p: str) -> bool:
    s = (p or "").lower()
    return s.endswith(".yaml") or s.endswith(".yml")

def _list_config_files(folder: Path) -> list[str]:
    files = [p.name for p in folder.glob("*.json")]
    files += [p.name for p in folder.glob("*.yaml")]
    files += [p.name for p in folder.glob("*.yml")]
    return sorted(files)

def first_cfg_in(folder: Path):
    cands = _list_config_files(folder)
    return (folder / cands[0]) if cands else None

# compute DEFAULT_CONFIG only after helpers exist
DEFAULT_CONFIG = Path(ENV.get("VEIN_CONFIG") or (first_cfg_in(CONFIG_DIR) or (CONFIG_DIR / "config.yaml")))

#----------------- config IO (YAML+JSON) --------------------------------------
from typing import Tuple as _Tuple
try:
    from ruamel.yaml import YAML  # comment-preserving round-trip
    _HAVE_RUAMEL = True
except Exception:
    _HAVE_RUAMEL = False

def _is_yaml_path(p: str) -> bool:
    s = (p or "").lower()
    return s.endswith(".yaml") or s.endswith(".yml")

def _setup_process_logging():
    """Redirect VeinManager stdout/stderr to Logs and capture crashes."""
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = LOGS_DIR / f"VeinManager.{ts}.stdout.log"
        err = LOGS_DIR / f"VeinManager.{ts}.stderr.log"

        sys.stdout = open(out, "w", buffering=1, encoding="utf-8", errors="replace")
        sys.stderr = open(err, "w", buffering=1, encoding="utf-8", errors="replace")

        # Python unhandled exceptions → stderr file
        def _excepthook(tp, val, tb):
            import traceback
            traceback.print_exception(tp, val, tb, file=sys.stderr)
            sys.stderr.flush()
        sys.excepthook = _excepthook

        # Qt messages → stderr file
        def _qt_msg_handler(mode, context, message):
            try:
                sys.stderr.write(f"[Qt] {message}\n")
                sys.stderr.flush()
            except Exception:
                pass
        try:
            QtCore.qInstallMessageHandler(_qt_msg_handler)  # PySide6
        except Exception:
            pass

        # Enable faulthandler if available
        try:
            import faulthandler
            faulthandler.enable(sys.stderr)
        except Exception:
            pass

        print("[VeinManager] Process logging initialized.")
        print(f"[VeinManager] stdout: {out}")
        print(f"[VeinManager] stderr: {err}")
        sys.stdout.flush()
    except Exception as e:
        # Last-ditch: don’t crash if logging setup fails
        print(f"[WARN] Failed to initialize process logging: {e}")

def _load_any_config(path: str):
    """
    Returns (obj, kind, ydoc) where:
      - obj: Python dict/list tree
      - kind: "yaml" or "json"
      - ydoc: ruamel.yaml round-trip doc if YAML (else None)
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return {}, "json", None
    txt = p.read_text(encoding="utf-8")
    if _is_yaml_path(path):
        if not _HAVE_RUAMEL:
            raise RuntimeError("YAML selected but ruamel.yaml is not installed.")
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        ydoc = y.load(txt)
        # ruamel can yield CommentedMap/Seq; treat it as 'obj'
        return ydoc, "yaml", ydoc
    else:
        import json
        return json.loads(txt), "json", None

def _dump_any_config(obj, kind: str, ydoc=None) -> str:
    from io import StringIO
    if kind == "yaml":
        if not _HAVE_RUAMEL:
            raise RuntimeError("Cannot write YAML without ruamel.yaml.")
        y = YAML()
        y.preserve_quotes = True
        y.width = 4096
        # When editing via KV rows we mutate ydoc (comment-preserving).
        # If only raw text changed, we won't call this.
        sio = StringIO()
        y.dump(ydoc if ydoc is not None else obj, sio)
        return sio.getvalue()
    else:
        import json
        return json.dumps(obj, indent=2)

def _list_config_files(folder: Path) -> list[str]:
    files = []
    files += [p.name for p in folder.glob("*.json")]
    files += [p.name for p in folder.glob("*.yaml")]
    files += [p.name for p in folder.glob("*.yml")]
    return sorted(files)

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

def spawn_logged(cmd: str, log_file: Path, cwd: Path | None = None, env: dict | None = None) -> subprocess.Popen:
    """
    Popen with stdout/stderr appended to a single log file.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(log_file, "a", encoding="utf-8", errors="replace")
    kw = {
        "shell": True,
        "cwd": str(cwd) if cwd else None,
        "stdout": f,
        "stderr": f,
        "text": True,
    }
    kw.update(_hidden_kwargs())
    if env is not None:
        kw["env"] = env
    return subprocess.Popen(cmd, **{k: v for k, v in kw.items() if v is not None})

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
    cfg = _load_cfg_for_runtime(cfg_path)
    rt = Path(cfg.get("runtime_dir") or RUNTIME_FALLBACK)
    return {
        "rt": rt,
        "pid_crash": rt / "crash_monitor.pid",
        "pid_log": rt / "log_monitor.pid",
        "stop_crash": rt / "stop_crash_monitor.flag",
        "stop_log": rt / "stop_log_monitor.flag",
        "state_crash": rt / "crash_monitor_state.json",
        "state_log": Path((cfg.get("monitor", {}) or {}).get("state_file") or (rt / "log_monitor_state.json")),
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
        obj, kind, _ = _load_any_config(cfg_path)
        return dict(obj) if isinstance(obj, dict) else {}
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
        vcfg = load_and_validate_config(cfg_path, fatal=False)
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
        """Read heartbeat knobs from the config (YAML or JSON)."""
        try:
            obj, kind, _ = _load_any_config(self.cfg_path)  # reuse the GUI's universal loader
            mon = (obj.get("monitor", {}) or {}) if isinstance(obj, dict) else {}
            hb = int(mon.get("heartbeat_seconds", mon.get("heartbeat_interval_seconds", 60)))
            fresh_mult = float(mon.get("fresh_window_multiplier", 2.0))
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

# ----------------------- YAML syntax highlight -------------------------------
class YamlHL(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.c = {}
    def highlightBlock(self, text):
        import re
        def f(hex): q = QtGui.QTextCharFormat(); q.setForeground(QtGui.QColor(hex)); return q
        self.c.setdefault("k", f("#7FB3D5"))   # keys
        self.c.setdefault("s", f("#ABEBC6"))   # strings
        self.c.setdefault("n", f("#F7DC6F"))   # numbers
        self.c.setdefault("b", f("#F5B7B1"))   # booleans
        self.c.setdefault("c", f("#7F8C8D"))   # comments
        # comments
        for m in re.finditer(r'\s#.*$', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["c"])
        # keys (key:)
        for m in re.finditer(r'^\s*([A-Za-z0-9_\-\.]+)\s*:(?!:)', text):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.c["k"])
        # quoted strings
        for m in re.finditer(r'\"([^\"\\]|\\.)*\"|\'([^\']|\\\')*\'', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["s"])
        # numbers
        for m in re.finditer(r'(?<![\w\.])(-?\d+(\.\d+)?)', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["n"])
        # booleans/null
        for m in re.finditer(r'\b(true|false|on|off|yes|no|null)\b', text, re.IGNORECASE):
            self.setFormat(m.start(), m.end() - m.start(), self.c["b"])


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
    
class CollapsibleBox(QtWidgets.QWidget):
    """Simple collapsible section with a header and a container layout."""
    def __init__(self, title: str):
        super().__init__()
        self._title_base = title
        self._count = 0

        self.toggle = QtWidgets.QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(QtCore.Qt.DownArrow)
        self.toggle.toggled.connect(self._on_toggled)

        self.header = QtWidgets.QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.addWidget(self.toggle)
        self.header.addStretch(1)

        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(8, 6, 8, 6)
        self.vbox.setSpacing(6)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.addLayout(self.header)
        outer.addWidget(self.container)

    def _on_toggled(self, on: bool):
        self.container.setVisible(on)
        self.toggle.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)

    def layout_for_rows(self) -> QtWidgets.QVBoxLayout:
        return self.vbox

    def set_count(self, n: int, active: bool):
        """Update header with a small count when filtering."""
        self._count = n
        suffix = f"  ({n})" if active else ""
        self.toggle.setText(self._title_base + suffix)

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

    def value(self):
        # checkbox
        if isinstance(self.editor, QtWidgets.QCheckBox):
            return bool(self.editor.isChecked())
        # line edits (inside the wrapper widget or direct)
        edits = self.editor.findChildren(QtWidgets.QLineEdit) or \
                ([self.editor] if isinstance(self.editor, QtWidgets.QLineEdit) else [])
        if edits:
            return edits[0].text()
        return None

    def scrollToMe(self):
        # simple focus helper used by search jump
        self.setFocus()

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

        self._sections_by_tab = collections.defaultdict(dict)   # type: dict[str, dict[str, CollapsibleBox]]
        self._rows_in_section = collections.defaultdict(list)   # type: dict[tuple[str, str], list[KVRow]]
        self._section_keys_by_tab: dict[str, set[str]] = {}

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

        # 4) config list + watch; first selection is applied after the combo is populated
        self.refresh_cfgs()
        self.watch_config()
        # Guarantee a real selection + load on first show
        QtCore.QTimer.singleShot(0, self._apply_default_selection)

        # 5) now it’s safe to start tailing
        self.tail_start()

        # 6) background status polling
        self._pool = QtCore.QThreadPool.globalInstance()
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._kick_status_poll)
        self._status_timer.start()

        self._restore_state()

        # Maps
        self._tab_base_titles = {i: self.tabs.tabText(i) for i in range(self.tabs.count())}
        self._tab_index_to_name = {i: self._tab_base_titles[i] for i in range(self.tabs.count())}

        # Row index by tab for search/result grouping
        self._rows_by_tab = collections.defaultdict(list)   # tab_name -> [KVRow]
        self._search_tab_name = "Search"
        self._search_tab_idx = None
        self._hl = None  # for syntax highlighter swap

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
        # LEFT: TABS
        left = QtWidgets.QWidget(); main.addWidget(left)
        lv = QtWidgets.QVBoxLayout(left); lv.setContentsMargins(0,0,0,0)

        # top bar (buttons + filter)
        topbar = QtWidgets.QHBoxLayout(); lv.addLayout(topbar)

        self.b_reload = QtWidgets.QPushButton("Reload Config")
        self.b_validate = QtWidgets.QPushButton("Validate")
        self.b_save = QtWidgets.QPushButton("Save Config (atomic)")
        self.filter = QtWidgets.QLineEdit(); self.filter.setPlaceholderText("Filter keys…")
        self.b_clearfilter = QtWidgets.QPushButton("Clear")

        # ... create self.b_reload, self.b_validate, self.b_save, self.filter, self.b_clearfilter
        topbar.addWidget(self.b_reload)
        topbar.addWidget(self.b_validate)
        topbar.addWidget(self.b_save)
        topbar.addStretch(1)
        topbar.addWidget(self.filter)
        topbar.addWidget(self.b_clearfilter)

        # CREATE THE TABS WIDGET
        self.tabs = QtWidgets.QTabWidget()
        lv.addWidget(self.tabs, 1)

        self.tab_widgets: Dict[str, QtWidgets.QWidget] = {}
        self.tab_layouts: Dict[str, QtWidgets.QVBoxLayout] = {}

        def _make_tab_ui():
            w = QtWidgets.QWidget()
            frame = QtWidgets.QVBoxLayout(w); frame.setContentsMargins(6,6,6,6); frame.setSpacing(6)
            scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
            container = QtWidgets.QWidget()
            vbox = QtWidgets.QVBoxLayout(container); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(6)
            scroll.setWidget(container)
            frame.addWidget(scroll, 1)
            return w, container, vbox

        def _add_tab(name: str):
            if name in self.tab_widgets:
                return
            w, container, vbox = _make_tab_ui()
            self.tabs.addTab(w, name)
            self.tab_widgets[name] = container
            self.tab_layouts[name] = vbox

        self._add_tab = _add_tab  # expose helper for later

        for name in ["Paths","Server","Steam/Updates","Backups","Monitor (simple)","Monitor (advanced)","Features","Top-level"]:
            _add_tab(name)

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

        # store the original tab titles by index for stable lookups/titles
        self._tab_base_titles = {i: self.tabs.tabText(i) for i in range(self.tabs.count())}
        # map index <-> base name so we can fetch the correct layout even if titles are decorated with counts
        self._tab_index_to_name = {i: self._tab_base_titles[i] for i in range(self.tabs.count())}

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
        self.lbl_watch = QtWidgets.QLabel("Watching for external config changes…"); v.addWidget(self.lbl_watch)

    # ----------------------------- Signals ------------------------------------
    def _signals(self):
        self.b_cfgdir.clicked.connect(self.pick_cfg_dir)
        self.b_reload_cfgs.clicked.connect(self.refresh_cfgs)
        self.cb_cfg.currentTextChanged.connect(self._cfg_selected)

        self.b_reload.clicked.connect(self.load_config_text)
        self.b_save.clicked.connect(self.save_atomic)
        self.b_validate.clicked.connect(self.validate_config)
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
        files = []
        self.cb_cfg.blockSignals(True); self.cb_cfg.clear()
        if folder.exists():
            files = _list_config_files(folder)
            self.cb_cfg.addItems(files)
            if files:
                cur = Path(self.config_path).name if self.config_path else ""
                chosen = cur if cur in files else files[0]
                self.cb_cfg.setCurrentText(chosen)
        self.cb_cfg.blockSignals(False)
        name = self.cb_cfg.currentText() or (files[0] if files else "")
        if name:
            self._cfg_selected(name)

    def _cfg_selected(self, name: str):
        if not name: return
        self.config_path = str(Path(self.ed_cfgdir.text().strip()).joinpath(name))
        self.load_config_text()
        self.watch_config()

    # -------------------------- Tab Helpers ---------------------------------
    def _strip_cnt(self, s: str) -> str:
        import re
        return re.sub(r"\s\(\d+\)$", "", s or "")

    def _rebuild_base_titles(self):
        self._tab_base_titles = {
            i: self._strip_cnt(self.tabs.tabText(i)) for i in range(self.tabs.count())
        }
        self._tab_index_to_name = dict(self._tab_base_titles)

    def _ensure_search_tab(self):
        names = [self._strip_cnt(self.tabs.tabText(i)) for i in range(self.tabs.count())]
        if self._search_tab_name in names:
            self._search_tab_idx = names.index(self._search_tab_name)
            return
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(6,6,6,6); v.setSpacing(4)
        v.addStretch(1)
        self.tabs.addTab(w, self._search_tab_name)
        self._rebuild_base_titles()
        self._search_tab_idx = self.tabs.count() - 1

    def _remove_search_tab(self):
        names = [self._strip_cnt(self.tabs.tabText(i)) for i in range(self.tabs.count())]
        if self._search_tab_name in names:
            idx = names.index(self._search_tab_name)
            self.tabs.removeTab(idx)
            self._search_tab_idx = None
            self._rebuild_base_titles()

    def _apply_default_selection(self):
        """Ensure a concrete file is selected and loaded at startup."""
        folder = Path(self.ed_cfgdir.text().strip() or self.config_dir)
        files = _list_config_files(folder)
        if not files:
            return
        want = Path(self.config_path).name if self.config_path else files[0]
        if want not in files:
            want = files[0]
        # setting text may or may not emit; we call the loader explicitly afterwards
        self.cb_cfg.blockSignals(True)
        self.cb_cfg.setCurrentText(want)
        self.cb_cfg.blockSignals(False)
        self._cfg_selected(want)

    # ------------------------------- JSON IO ----------------------------------
    def load_config_text(self):
        self._yaml_doc = None
        self._cfg_kind = "json"
        try:
            obj, kind, ydoc = _load_any_config(self.config_path)
            self._cfg_kind = kind
            self._yaml_doc = ydoc
            self._data = obj if isinstance(obj, dict) else {}
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = f.read()
            self.json.blockSignals(True)
            self.json.setPlainText(raw)
            # swap highlighter
            if hasattr(self, "_hl") and self._hl:
                self._hl.setDocument(None)
            self._hl = YamlHL(self.json.document()) if kind == "yaml" else JsonHL(self.json.document())
            self.json.blockSignals(False)
            self._build_tabs(self._data)
            self._rebuild_base_titles()
            self._status(f"Loaded {kind.upper()}.")
        except Exception as e:
            self._data = {}
            self.json.setPlainText("")
            self._status(f"Load error: {e}")

    # --- label helpers used by tab-building ---------------------------------
    def _humanize_label(self, s: str) -> str:
        import re
        s = (s or "").replace("_", " ").replace(".", "•")
        s = re.sub(r"\s+", " ", s).strip()
        return s.title()

    def _pretty_label(self, tab: str, full_label: str) -> str:
        """Trim the tab's key prefix from a dotted label and title-case it."""
        base = tab.lower().replace(" ", "_")
        if base in ("top-level", "paths", "monitors", getattr(self, "_search_tab_name", "search").lower()):
            return self._humanize_label(full_label)
        low = full_label.lower()
        pref = base + "."
        trimmed = full_label[len(pref):] if low.startswith(pref) else full_label
        return self._humanize_label(trimmed)

    def _add_row_to_tab_or_section(self, tab: str, full_label: str,
                               path: tuple[str, ...], val):
        self._add_tab(tab)

        # Only sectionize if the tab corresponds to path[0] AND the second-level key is a dict.
        def _snake(s: str) -> str:
            return (s or "").strip().lower().replace(" ", "_")

        tab_base_snake = _snake(tab)
        path0_snake = _snake(path[0]) if path else ""
        # candidates determined earlier in _build_tabs:
        section_keys = self._section_keys_by_tab.get(tab, set())

        section_key = None
        if (tab_base_snake == path0_snake and len(path) >= 2):
            k2 = str(path[1])
            if k2 in section_keys:
                section_key = k2

        # Choose layout: section container or tab root
        if section_key is None:
            layout = self.tab_layouts[tab]
        else:
            if section_key not in self._sections_by_tab[tab]:
                box = CollapsibleBox(self._humanize_label(section_key))
                self._sections_by_tab[tab][section_key] = box
                self.tab_layouts[tab].addWidget(box)
            layout = self._sections_by_tab[tab][section_key].layout_for_rows()

        # Pretty label: trim 'Tab.' or 'Tab.Section.' prefix, then title-case
        base = tab.lower().replace(" ", "_")
        low = full_label.lower()
        trimmed = full_label
        if section_key is not None:
            pref = f"{base}.{section_key.lower()}."
            if low.startswith(pref):
                trimmed = full_label[len(pref):]
        else:
            pref = base + "."
            if low.startswith(pref):
                trimmed = full_label[len(pref):]

        label = self._humanize_label(trimmed)
        row = KVRow(label, path, val)
        row.changed.connect(self._row_changed)
        
        indent = max(0, len(path) - (2 if section_key else 1))
        if indent and hasattr(row, "layout"):
            row.layout().setContentsMargins(12 * indent, 0, 0, 0)

        layout.addWidget(row)

        self.rows[path] = row
        self._rows_by_tab[tab].append(row)
        if section_key is not None:
            self._rows_in_section[(tab, section_key)].append(row)

    def _build_tabs(self, data: dict):
        """Auto-build tabs from the config hierarchy.

        Rules:
        - Every top-level key that's a dict → its own tab (Title Cased).
        - Top-level scalars → 'Top-level' tab.
        - Nested dicts are flattened to dotted keys within their parent tab.
        - Lists are rendered as comma-joined strings (still editable).
        """
        self._sections_by_tab.clear()
        self._rows_in_section.clear()

        # Remove all dynamic tabs (keep Monitors and Search if present)
        fixed = {"Monitors", getattr(self, "_search_tab_name", "Search")}
        for i in reversed(range(self.tabs.count())):
            base = self._strip_cnt(self.tabs.tabText(i))
            if base not in fixed:
                self.tabs.removeTab(i)

        # clear existing row widgets BEFORE wiping the registries
        for vbox in self.tab_layouts.values():
            while vbox.count():
                w = vbox.takeAt(0).widget()
                if w: w.deleteLater()

        # reset dynamic tab registries
        self.tab_widgets.clear()
        self.tab_layouts.clear()
        self._rows_by_tab.clear()
        self.rows.clear()

        # Ensure a Top-level tab exists for scalars
        self._add_tab("Top-level")

        def tab_name_for_top_key(k: str) -> str:
            # Pretty name (e.g., 'nightly_backup' -> 'Nightly Backup')
            if not k: return "Top-level"
            name = k.replace("_", " ").strip().title()
            return name

        def looks_path_key(k: str) -> bool:
            k = (k or "").lower()
            return any(t in k for t in ("path", "file", "dir", "folder", "root"))

        def flatten_into_tab(tab: str, prefix: tuple[str, ...], node: Any):
            if isinstance(node, dict):
                for ck in sorted(node.keys(), key=lambda s: str(s)):
                    flatten_into_tab(tab, prefix + (ck,), node[ck])
                return
            label = ".".join(prefix)
            val = node if not isinstance(node, list) else ", ".join(str(x) for x in node)
            self._add_row_to_tab_or_section(tab, label, prefix, val)

        # 1) Top-level pass: scalars → Top-level, dicts → own tab
        dict_tabs: list[tuple[str, dict]] = []
        for k in sorted(data.keys(), key=lambda s: str(s)):
            v = data[k]
            if isinstance(v, dict):
                dict_tabs.append((k, v))
            else:
                self._add_row_to_tab_or_section("Top-level", k, (k,), v)

        # 2) For each top-level dict, flatten into its own tab
        for k, node in dict_tabs:
            tname = tab_name_for_top_key(k)
            # Decide which second-level keys become collapsible sections:
            # Only dict-valued children one level below the tab root.
            section_keys = {str(ck) for ck, cv in (node.items() if isinstance(node, dict) else [])
                            if isinstance(cv, dict)}
            self._section_keys_by_tab[tname] = section_keys

            if k == "features" and isinstance(node, dict):
                # show just "enable_log_monitor", etc.
                for fk in sorted(node.keys(), key=lambda s: str(s)):
                    label = f"{k}.{fk}"                   # becomes just "enable_log_monitor" by _pretty_label
                    self._add_row_to_tab_or_section(tname, label, (k, fk), node[fk])
            else:
                flatten_into_tab(tname, (k,), node)
        # 3) Paths convenience: if many 'path/dir' top-level keys exist, also mirror them into a 'Paths' tab
        path_keys = [(k, data[k]) for k in data.keys() if not isinstance(data[k], dict) and looks_path_key(k)]
        if path_keys:
            self._add_tab("Paths")
            for k, v in sorted(path_keys, key=lambda kv: kv[0]):
                self._add_row_to_tab_or_section("Paths", k, (k,), v)

        # 4) Stretchers and filter pass
        for vbox in self.tab_layouts.values():
            vbox.addStretch(1)
        self._apply_filter(self.filter.text())

    def _collect_matches(self, text: str, include_values: bool = True):
        """Return list[(tab_name, KVRow)] that match the filter."""
        t = (text or "").strip().lower()
        if not t:
            return []
        hits = []
        for tab_name, rows in self._rows_by_tab.items():
            for r in rows:
                label = r.label_text.lower()
                ok = (t in label)
                if not ok and include_values:
                    try:
                        val_s = str(r.value()).lower()
                        ok = t in val_s
                    except Exception:
                        ok = False
                if ok:
                    hits.append((tab_name, r))
        return hits

    def _populate_search_tab(self, text: str):
        if not text:
            self._remove_search_tab()
            return

        self._ensure_search_tab()
        w = self.tabs.widget(self._search_tab_idx)
        lay = w.layout()

        # Clear existing widgets
        while lay.count() > 0:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Group matches by their source tab
        groups = defaultdict(list)
        for tab_name, row in self._collect_matches(text, include_values=True):
            groups[tab_name].append(row)

        if not groups:
            lay.addWidget(QtWidgets.QLabel(f"No matches for “{text}”."))
            lay.addStretch(1)
            self.tabs.setCurrentIndex(self._search_tab_idx)
            return

        def jump_to_row(tab_name: str, row: "KVRow"):
            # Switch to original tab and focus the row
            idx = None
            for i in range(self.tabs.count()):
                base = self._tab_base_titles.get(i) or self.tabs.tabText(i)
                if base == tab_name or self.tabs.tabText(i).startswith(tab_name):
                    idx = i
                    break
            if idx is not None:
                self.tabs.setCurrentIndex(idx)
            row.setVisible(True)
            if hasattr(row, "scrollToMe"):
                row.scrollToMe()
            row.setStyleSheet("background-color:#264653;")
            QtCore.QTimer.singleShot(300, lambda: row.setStyleSheet(""))

        # Build grouped result list
        for tab_name in sorted(groups.keys()):
            lay.addWidget(QtWidgets.QLabel(f"<b>{tab_name}</b>"))
            for r in groups[tab_name]:
                txt = f"{r.label_text}   →   {str(r.value())[:80]}"
                btn = QtWidgets.QPushButton(txt)
                btn.setCursor(QtCore.Qt.PointingHandCursor)
                btn.setToolTip("Jump to original")
                btn.clicked.connect(lambda _, tn=tab_name, row=r: jump_to_row(tn, row))
                lay.addWidget(btn)

        lay.addStretch(1)
        # Show Search tab automatically while filtering
        self.tabs.setCurrentIndex(self._search_tab_idx)

    def _row_changed(self, path: Tuple[str, ...], val: Any):
        # 1) update the in-memory dict (used to rebuild tabs/filter/etc.)
        cur = self._data
        for p in path[:-1]:
            if p not in cur or not isinstance(cur[p], dict):
                cur[p] = {}
            cur = cur[p]
        cur[path[-1]] = val

        # 2) also reflect the change into the round-trip YAML doc when applicable
        if self._cfg_kind == "yaml" and self._yaml_doc is not None:
            ycur = self._yaml_doc
            try:
                for p in path[:-1]:
                    if p not in ycur or not hasattr(ycur[p], "keys"):
                        ycur[p] = {}  # ruamel will create a CommentedMap
                    ycur = ycur[p]
                ycur[path[-1]] = val
                new_text = _dump_any_config(self._data, "yaml", ydoc=self._yaml_doc)
            except Exception:
                # fall back to raw text (do nothing)
                new_text = self.json.toPlainText()
        else:
            # JSON: re-dump pretty
            new_text = _dump_any_config(self._data, "json")

        # 3) push text to the editor (this is what Save uses)
        self.json.blockSignals(True)
        self.json.setPlainText(new_text)
        self.json.blockSignals(False)

    def validate_config(self):
        try:
            if _is_yaml_path(self.config_path):
                if not _HAVE_RUAMEL: raise RuntimeError("ruamel.yaml not installed")
                y = YAML(); y.preserve_quotes = True
                y.load(self.json.toPlainText())
            else:
                import json as _json
                _json.loads(self.json.toPlainText())
            self._status("Config parses ✅")
        except Exception as e:
            self._status(f"Parse error: {e}")

    def save_atomic(self):
        """Save exactly what’s in the text editor. (KV edits keep text in sync.)"""
        try:
            path = Path(self.config_path)
            tmp = path.with_suffix(path.suffix + ".tmp")
            self._saving = True
            with tmp.open("w", encoding="utf-8") as f:
                f.write(self.json.toPlainText())
            os.replace(tmp, path)
            self._status("Saved atomically.")
        except Exception as e:
            self._status(f"Save failed: {e}")
        finally:
            QtCore.QTimer.singleShot(250, lambda: setattr(self, "_saving", False))

    # ---------------------------- Watch / tail --------------------------------
    def watch_config(self):
        try:
            if hasattr(self, "watcher"):
                for p in self.watcher.files():
                    try: self.watcher.removePath(p)
                    except Exception: pass
            self.watcher = QtCore.QFileSystemWatcher(self)
            if Path(self.config_path).exists():
                self.watcher.addPath(self.config_path)
            self.watcher.fileChanged.connect(lambda _:
                (self._saving and None) or QtCore.QTimer.singleShot(300, self.load_config_text))
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
        srv_stdout = LOGS_DIR / "server.stdout.log"
        try:
            spawn_logged(f'{_pyexe()} "{py}"', srv_stdout, py.parent, env=env)
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
            if out:
                (LOGS_DIR / "vein_manager.subproc.out.log").write_text(out, encoding="utf-8")
            if err:
                (LOGS_DIR / "vein_manager.subproc.err.log").write_text(err, encoding="utf-8")
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

        # Write monitor stdout/stderr here:
        lm_stdout = LOGS_DIR / "monitor_log.stdout.log"
        try:
            spawn_logged(f'{_pyexe()} "{mon_py}" --follow', lm_stdout, mon_py.parent, env=env)
            self._status("Log monitor starting…")
        except Exception as e:
            self._status(f"Log monitor start failed: {e}")

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

        cm_stdout = LOGS_DIR / "crash_monitor.stdout.log"
        try:
            spawn_logged(f'{_pyexe()} "{cm_py}"', cm_stdout, cm_py.parent, env=env)
            self._status("Crash monitor starting…")
        except Exception as e:
            self._status(f"Crash monitor start failed: {e}")

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

        # Visibility pass for rows (so the left-side panels still filter)
        for path, row in self.rows.items():
            label = row.label_text.lower()
            show = (t in label) if t else True
            if not show and t:
                # also match values to hide/show left-side rows consistently
                try:
                    show = t in str(row.value()).lower()
                except Exception:
                    pass
            row.setVisible(show)

        # Count matches per tab using the index (not relying on current visibility)
        all_hits = self._collect_matches(t, include_values=True) if t else []
        counts_by_tabname = {}
        for tab_name, _row in all_hits:
            counts_by_tabname[tab_name] = counts_by_tabname.get(tab_name, 0) + 1

        for i in range(self.tabs.count()):
            base = self._tab_base_titles.get(i, self._strip_cnt(self.tabs.tabText(i)))
            if not t:
                self.tabs.setTabText(i, base)
                continue
            cnt = len(all_hits) if base == self._search_tab_name else counts_by_tabname.get(base, 0)
            self.tabs.setTabText(i, f"{base} ({cnt})")

        # Populate or remove the Search tab
        if t:
            self._populate_search_tab(t)
        else:
            self._remove_search_tab()

        # Update section counts and visibility
        active_filter = bool(t)
        for (tab, section), rows in self._rows_in_section.items():
            visible = [r for r in rows if r.isVisible()]
            box = self._sections_by_tab.get(tab, {}).get(section)
            if not box:
                continue
            box.setVisible(len(visible) > 0 or not active_filter)  # hide empty sections when filtering
            box.set_count(len(visible), active_filter)


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
    _setup_process_logging()
    app = QtWidgets.QApplication(sys.argv)
    if os.name == "nt":
        app.setStyle("Fusion")
    w = Main(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
