# vein_manager.py — Vein Server Manager (clean header + Monitors tab + Advanced Overrides)
from __future__ import annotations

# --- stdlib imports first
import json, os, sys, subprocess, time, re
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional, Callable
from datetime import datetime, timezone
import collections

# --- Qt
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

try:
    from ruamel.yaml import YAML

    _HAVE_RUAMEL = True
except Exception:
    _HAVE_RUAMEL = False

# ----------------------------- Environment -----------------------------------
ENV = os.environ


def _default_root() -> Path:
    """Determine the management root for editable resources."""
    if ENV.get("VEIN_MGMT_ROOT"):
        return Path(ENV["VEIN_MGMT_ROOT"])
    if getattr(sys, "frozen", False):
        # When packaged (PyInstaller) prefer the directory that contains the exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


ROOT = _default_root()
CONFIG_DIR = ROOT / "Config"
CTRL_DIR = ROOT / "Controller"
RUNTIME_FALLBACK = ROOT / "Runtime"
PYEXE_ENV = ENV.get("PYEXE", "")
APP_ORG = "RHG"
APP_NAME = "VeinManager"
# Ensure we can import Tools/* even if PYTHONPATH wasn't set by the .bat
if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))

# Now it is safe to import Tools modules
try:
    from Tools.config_io import load_and_validate_config
    from Tools import mgmt_logs, log_search, log_events
except Exception as e:
    print(f"[FATAL] Could not import Tools components from {CTRL_DIR}: {e}")
    sys.exit(1)

try:
    from GUI import (
        NavigationItem,
        NavigationPanel,
        build_config_editor,
        build_dashboard,
        build_command_bar,
        build_left_panel,
        build_log_panel,
    build_placeholder_view,
    CollapsibleBox,
    KVRow,
    handle_player_tree_double_click,
    StatusBus,
    StatusPoller,
    ConfigRenderer,
) 
except Exception as e:
    print(f"[FATAL] Could not import Controller.GUI components: {e}")
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
DEFAULT_CONFIG = Path(
    ENV.get("VEIN_CONFIG") or (first_cfg_in(CONFIG_DIR) or (CONFIG_DIR / "config.yaml"))
)

# ----------------- config IO (YAML+JSON) --------------------------------------
from typing import Tuple as _Tuple


def _setup_process_logging():
    """Redirect VeinManager stdout/stderr to Logs and capture crashes."""
    try:
        files = mgmt_logs.allocate_stream_files(
            "vein_manager",
            label="VeinManager",
            streams=("stdout", "stderr"),
            metadata={"pid": os.getpid(), "source": "vein_manager"},
        )
        out = files["stdout"]
        err = files["stderr"]

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


# --- Config loading that preserves YAML order+comments -----------------------
from pathlib import Path

# --- Config loading that preserves YAML order+comments -----------------------
from pathlib import Path


def _load_any_config(path: str | Path):
    """
    Returns a triple: (obj_dict, kind_str, yaml_doc_or_None)
    - kind_str: 'yaml' or 'json'
    - yaml_doc_or_None: ruamel.yaml CommentedMap when YAML, else None
    """
    p = Path(path)
    txt = p.read_text(encoding="utf-8")
    suf = p.suffix.lower()
    if suf in (".yaml", ".yml"):
        if not _HAVE_RUAMEL:
            raise RuntimeError("YAML config selected but ruamel.yaml is not installed")
        y = YAML()
        y.preserve_quotes = True
        doc = y.load(txt)
        data = dict(doc) if isinstance(doc, dict) else {}
        return data, "yaml", doc
    else:
        import json as _json

        data = _json.loads(txt) if txt.strip() else {}
        return data, "json", None


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


# ------------------------- Subprocess helpers --------------------------------
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _hidden_kwargs():
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return {"startupinfo": si, "creationflags": CREATE_NO_WINDOW}


def spawn(
    cmd: str, cwd: Path | None = None, env: dict | None = None
) -> subprocess.Popen:
    kw = {"shell": True, "cwd": str(cwd) if cwd else None}
    kw.update(_hidden_kwargs())
    if env is not None:
        kw["env"] = env
    return subprocess.Popen(cmd, **{k: v for k, v in kw.items() if v is not None})


def run_once(cmd: str, cwd: Path | None = None, timeout=60, env: dict | None = None):
    kw = {
        "shell": True,
        "cwd": str(cwd) if cwd else None,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
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


def spawn_logged(
    cmd: str, log_file: Path, cwd: Path | None = None, env: dict | None = None
) -> subprocess.Popen:
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
    if os.name != "nt" or not image_name.strip():
        return False
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
        kw = {"text": True}
        kw.update(_hidden_kwargs())
        out = subprocess.check_output(cmd, **kw).strip()
        return bool(out)
    except Exception:
        return False


# --------------------------- Runtime helpers ---------------------------------
def _rt_paths(cfg_path: str) -> dict:
    cfg = _load_cfg_for_runtime(cfg_path)
    rt = Path(cfg.get("runtime_dir") or RUNTIME_FALLBACK)
    monitor_cfg = cfg.get("monitor") or {}
    state_candidates: list[Path] = []
    cfg_state = monitor_cfg.get("state_file")
    if isinstance(cfg_state, str) and cfg_state.strip():
        state_candidates.append(Path(cfg_state.strip()))
    state_candidates.append(rt / "log_monitor.state.json")
    state_candidates.append(rt / "log_monitor_state.json")

    state_path = state_candidates[0]
    for cand in state_candidates:
        try:
            if cand.exists():
                state_path = cand
                break
        except Exception:
            continue

    return {
        "rt": rt,
        "pid_crash": rt / "crash_monitor.pid",
        "pid_log": rt / "log_monitor.pid",
        "stop_crash": rt / "stop_crash_monitor.flag",
        "stop_log": rt / "stop_log_monitor.flag",
        "state_crash": rt / "crash_monitor_state.json",
        "state_log": state_path,
        "player_snapshot": rt / "player_characters.json",
    }


def _file_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _mkflag(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text("", encoding="utf-8")
    except Exception:
        pass


def _rm(p: Path):
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def _pid_alive(pid_str: str | None) -> bool:
    if not pid_str:
        return False
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

    # prefer nested 'backups.root' from YAML, then fallback to legacy top-level
    b = cfg.get("backups", {}) or {}
    b_root = b.get("root")
    legacy = cfg.get("backup_root")
    backup_root = Path(b_root or legacy or (ROOT / "Backups"))

    # Heartbeat seconds used by freshness window (prefer top-level; fallback to nested; else 60)
    hb_top = cfg.get("monitor_heartbeat_interval_seconds", None)
    hb_nested = (cfg.get("monitor", {}) or {}).get("heartbeat_interval_seconds", None)
    try:
        hb = int(
            hb_top
            if hb_top is not None
            else (hb_nested if hb_nested is not None else 60)
        )
    except Exception:
        hb = 60

    monitor = cfg.get("monitor", {}) if isinstance(cfg.get("monitor", {}), dict) else {}

    return {
        "runtime_dir": rt,
        "state_flag": rt / "server_running.flag",
        "shutdown_flag": rt / "shutdown_in_progress.flag",
        "server_state": rt / "server_state.json",
        "crash_state": rt / "crash_monitor_state.json",
        "logs_dir": Path(
            cfg.get("logs_dir") or (server_dir / "Vein" / "Saved" / "Logs")
        ),
        "absolute_log_file": (
            Path(cfg.get("absolute_log_file")) if cfg.get("absolute_log_file") else None
        ),
        "backup_root": backup_root,
        "features": cfg.get("features", {}),
        "log_monitor_enabled": bool(
            cfg.get("features", {}).get("enable_log_monitor", True)
        ),
        "crash_monitor_enabled": bool(
            cfg.get("features", {}).get("enable_crash_monitor", True)
        ),
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
    try:
        return p.exists()
    except Exception:
        return False


def _dot(on: bool, warn: bool = False) -> str:
    if warn:
        return "background:#EFB700; border-radius:6px; min-width:12px; min-height:12px;"
    return f"background:{'#2ECC71' if on else '#E74C3C'};border-radius:6px;min-width:12px;min-height:12px;"


def _age_str(iso_ts: str | None) -> str:
    if not iso_ts:
        return "—"
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        sec = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        if sec < 60:
            return f"{sec}s"
        if sec < 3600:
            return f"{sec//60}m {sec%60}s"
        return f"{sec//3600}h {(sec%3600)//60}m"
    except Exception:
        return "—"



    def _runtime_paths_v2(self) -> dict:
        rd = Path(self.paths.get("runtime_dir", "") or "")
        return {
            "runtime_dir": rd,
            # New unified name used by utils/Tools.state_io
            "server_state": rd / "server_state.json",
            # Fallback JSON flag (not critical now, but kept for compatibility)
            "state_flag": rd / "intent.json",
        }

    def _rt_paths_v2(self) -> dict:
        rd = Path(self.paths.get("runtime_dir", "") or "")
        return {
            "pid_log": rd / "log_monitor.pid",
            "pid_crash": rd / "crash_monitor.pid",
            "state_log": rd / "log_monitor.state.json",
            "state_crash": rd / "crash_monitor.state.json",
        }

    def _read_text(self, p: Path) -> str | None:
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            return None

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
            out = subprocess.check_output(
                ["tasklist"], text=True, creationflags=CREATE_NO_WINDOW
            )
            # naive but robust: look for the pid as a standalone token
            needle = f" {pid} "
            return any(needle in (" " + line + " ") for line in out.splitlines())
        except Exception:
            return False

    def _hb_knobs(self) -> tuple[int, float]:
        """Read heartbeat knobs from config; v2 'log_monitor' first, fallback to 'monitor'."""
        try:
            obj, kind, _ = _load_any_config(self.cfg_path)
            obj = obj if isinstance(obj, dict) else {}
            lm = obj.get("log_monitor", {}) or {}
            mon = obj.get("monitor", {}) or {}
            hb = int(
                lm.get(
                    "heartbeat_seconds",
                    lm.get(
                        "heartbeat_interval_seconds",
                        mon.get(
                            "heartbeat_seconds",
                            mon.get("heartbeat_interval_seconds", self.hb_seconds),
                        ),
                    ),
                )
            )
            hb = max(5, hb)
            fresh_mult = float(
                lm.get(
                    "fresh_window_multiplier",
                    mon.get("fresh_window_multiplier", self.fresh_mult),
                )
            )
            fresh_mult = max(0.25, min(10.0, fresh_mult))
            return hb, fresh_mult
        except Exception:
            return self.hb_seconds, self.fresh_mult

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
        try:
            if self.stop_flag:
                return

            rp = self._runtime_paths_v2()
            rt = self._rt_paths_v2()
            hb_seconds, fresh_mult = self._hb_knobs()

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
            mode = (
                (cs.get("status") or cs.get("mode") or "unknown") if cs else "unknown"
            )

            # Load config object once; very cheap and we already do it elsewhere
            cfg_obj, _, _ = _load_any_config(self.cfg_path)
            b = (cfg_obj.get("backups", {}) or {}) if isinstance(cfg_obj, dict) else {}
            enabled = bool(b.get("enable", True))

            # --- Backup state (optional if file missing) ---
            backup_state_path = rp["runtime_dir"] / "backup.state.json"
            bk = self._read_json(backup_state_path)

            snapshot_backup = {
                "enabled": enabled,
                "last_utc": bk.get("last_utc") or bk.get("last_updated"),
                "last_zip": bk.get("last_zip"),
                "root": bk.get("root"),
                "counts": bk.get("counts") or {},
            }

            # ...then include it in the emitted dict:
            payload = {
                "server": bool(srv_on),
                "logmon": bool(lm_on),
                "logmon_fresh": bool(lm_fresh),
                "crashmon": bool(cm_on),
                "crash_mode": mode,
                "backup": snapshot_backup,
            }

            # Emit compact snapshot consumed by the UI
            self.signals.ready.emit(payload)

            if self.stop_flag:
                return
            if self.signals is not None:
                # queued to the main thread automatically
                self.signals.ready.emit(payload)
        except Exception:
            # never crash the GUI thread if the poller hiccups
            pass


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
            return (
                (size < old_size)
                or (size == 0 and old_size > 0)
                or (mt != old_mt and size < old_size)
            )
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


# ------------------------ Log search worker ---------------------------------
class LogSearchWorker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        ready = QtCore.Signal(list)
        error = QtCore.Signal(str)

    def __init__(
        self,
        *,
        subsystems: Optional[List[str]],
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
        subsystems: Optional[List[str]],
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


# ----------------------- JSON syntax highlight -------------------------------
class JsonHL(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.c = {}

    def highlightBlock(self, text):
        import re

        def f(hex):
            q = QtGui.QTextCharFormat()
            q.setForeground(QtGui.QColor(hex))
            return q

        self.c.setdefault("k", f("#7FB3D5"))
        self.c.setdefault("s", f("#ABEBC6"))
        self.c.setdefault("n", f("#F7DC6F"))
        self.c.setdefault("b", f("#F5B7B1"))
        self.c.setdefault("0", f("#D2B4DE"))
        for m in re.finditer(r'\"([^"]+)\"\s*(?=:\s)', text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["k"])
        for m in re.finditer(r"\"([^\"\\]|\\.)*\"", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["s"])
        for m in re.finditer(r"(?<![\w\.])(-?\d+(\.\d+)?)", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["n"])
        for m in re.finditer(r"\b(true|false)\b", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["b"])
        for m in re.finditer(r"\bnull\b", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["0"])


# ----------------------- YAML syntax highlight -------------------------------
class YamlHL(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.c = {}

    def highlightBlock(self, text):
        import re

        def f(hex):
            q = QtGui.QTextCharFormat()
            q.setForeground(QtGui.QColor(hex))
            return q

        self.c.setdefault("k", f("#7FB3D5"))  # keys
        self.c.setdefault("s", f("#ABEBC6"))  # strings
        self.c.setdefault("n", f("#F7DC6F"))  # numbers
        self.c.setdefault("b", f("#F5B7B1"))  # booleans
        self.c.setdefault("c", f("#7F8C8D"))  # comments
        # comments
        for m in re.finditer(r"\s#.*$", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["c"])
        # keys (key:)
        for m in re.finditer(r"^\s*([A-Za-z0-9_\-\.]+)\s*:(?!:)", text):
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.c["k"])
        # quoted strings
        for m in re.finditer(r"\"([^\"\\]|\\.)*\"|\'([^\']|\\\')*\'", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["s"])
        # numbers
        for m in re.finditer(r"(?<![\w\.])(-?\d+(\.\d+)?)", text):
            self.setFormat(m.start(), m.end() - m.start(), self.c["n"])
        # booleans/null
        for m in re.finditer(
            r"\b(true|false|on|off|yes|no|null)\b", text, re.IGNORECASE
        ):
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
        self.chk_use_defaults = QtWidgets.QCheckBox(
            "Use defaults from config (ignore overrides)"
        )
        v.addWidget(self.chk_use_defaults)

        grid = QtWidgets.QGridLayout()
        v.addLayout(grid)
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
            btn = QtWidgets.QToolButton()
            btn.setText("…")
            btn.clicked.connect(lambda _=None, k=key, e=le: self._pick(k, e))
            grid.addWidget(le, row, 1)
            grid.addWidget(btn, row, 2)
            self.edits[key] = le
            row += 1

        bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
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
            p, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select log file", cur, "Log files (*.log *.txt);;All files (*.*)"
            )
            if p:
                le.setText(p)
        else:
            p, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Select python script", cur, "Python (*.py);;All files (*.*)"
            )
            if p:
                le.setText(p)

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
            le.setText(str(ov.get(k, "" if k == "log_file" else resolved.get(k, ""))))

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
# ------------------------------ Main window ----------------------------------
class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vein Server Manager")
        self.resize(1380, 900)
        self.setMinimumSize(1200, 720)  # keep the frame from collapsing/expanding

        # basic state
        self.config_dir = str(CONFIG_DIR)
        self.config_path = str(DEFAULT_CONFIG)
        self.rows = {}
        self._saving = False

        self._sections_by_tab = collections.defaultdict(
            dict
        )  # type: dict[str, dict[str, CollapsibleBox]]
        self._rows_in_section = collections.defaultdict(
            list
        )  # type: dict[tuple[str, str], list[KVRow]]

        # settings
        q = QtCore.QSettings(APP_ORG, APP_NAME)
        self.use_defaults = bool(q.value("use_defaults", True))
        self.overrides = dict(q.value("overrides", {}) or {})

        # Structures needed while building the UI
        self._rows_by_tab = collections.defaultdict(list)  # tab_name -> [KVRow]
        self._search_tab_name = "Search"
        self._hl = None  # syntax highlighter holder for JSON editor

        self._player_tree_signature = None
        self._status_icon_cache = {}

        # 1) build UI (creates tabs + self.chk_live, self.log_game/self.log_lm/self.log_cm)
        self._ui()

        # config renderer handles tab + filter state
        self.config_renderer = ConfigRenderer(self)

        # 2) signals
        self._signals()  # should connect: b_clearlog-> _clear_current_log, chk_live-> _retail

        # 3) init NEW 3-tab tail buffers/handles BEFORE tail_start()
        self._buf_game, self._buf_lm, self._buf_cm = [], [], []
        self.tail_game = None
        self.tail_lm = None
        self.tail_cm = None

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
        self.status_bus = StatusBus(self)  # parented to the main window
        self.status_bus.ready.connect(self._status)
        self._pool = QtCore.QThreadPool.globalInstance()
        self._log_search_running = False
        self._error_refresh_running = False
        self._archiving_logs = False
        self._log_search_worker = None
        self._error_worker = None
        self._archive_worker = None
        self._poller = None
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._kick_status_poll)
        self._status_timer.start()

        self._restore_state()

        # Maps
        self._tab_base_titles = {
            i: self.tabs.tabText(i) for i in range(self.tabs.count())
        }
        self._tab_index_to_name = {
            i: self._tab_base_titles[i] for i in range(self.tabs.count())
        }

        # ------------------------------- UI --------------------------------------
    def _ui(self):
        container = QtWidgets.QWidget()
        self.setCentralWidget(container)
        root = QtWidgets.QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(build_command_bar(self, _dot))

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        root.addWidget(self.main_splitter, 1)

        monitor_items = [
            NavigationItem(
                "monitor.dashboard",
                "Server Dashboard",
                "Live server stats, monitors, and players",
            )
        ]
        config_nav_data = [
            ("config.paths", "Paths", "Server + runtime directories"),
            ("config.server", "Server", "Launch arguments and gameplay rules"),
            ("config.steam", "Steam/Updates", "SteamCMD + update settings"),
            ("config.backups", "Backups", "Schedules and retention"),
            ("config.monitor_simple", "Monitor (simple)", "Legacy monitor toggles"),
            ("config.monitor_adv", "Monitor (advanced)", "Advanced monitor settings"),
            ("config.features", "Features", "Feature flags and integrations"),
            ("config.top", "Top-level", "Loose scalar keys"),
            ("config.search", self._search_tab_name, "Quick search results"),
        ]
        self._config_nav_map = {vid: tab for vid, tab, _ in config_nav_data}
        config_items = [NavigationItem(vid, label, subtitle) for vid, label, subtitle in config_nav_data]

        self.nav_panel = NavigationPanel(monitor_items, config_items)
        left_panel = build_left_panel(self, self.nav_panel)
        self.main_splitter.addWidget(left_panel)

        self.content_stack = QtWidgets.QStackedWidget()
        self.main_splitter.addWidget(self.content_stack)

        log_panel = build_log_panel(self)
        self.main_splitter.addWidget(log_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setCollapsible(2, True)
        self._populate_log_sources()

        self._view_routes: dict[str, tuple[QtWidgets.QWidget, Optional[Callable[[], None]]]] = {}
        self._cached_admin_ids: set[str] | None = None
        dashboard = build_dashboard(self, _dot)
        self._register_view("monitor.dashboard", dashboard)

        diag_placeholder = build_placeholder_view(
            "Monitor diagnostics view is under construction."
        )
        self._register_view("monitor.diagnostics", diag_placeholder)

        discord_placeholder = build_placeholder_view(
            "Discord integration UI will live here once the backend is ready."
        )
        self._register_view("monitor.discord", discord_placeholder)

        config_view = build_config_editor(self)
        JsonHL(self.json.document())
        for view_id, tab_name in self._config_nav_map.items():
            self._register_view(
                view_id,
                config_view,
                lambda tab=tab_name: self._ensure_tab_visible(tab),
            )

        self.nav_panel.viewSelected.connect(self._on_view_selected)
        self.nav_panel.set_default_selection("monitor.dashboard")
        self._on_view_selected("monitor.dashboard")

        bottom = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 6, 0, 0)
        bottom_layout.setSpacing(8)

        self.state_box = QtWidgets.QTextBrowser()
        self.state_box.setMaximumHeight(120)
        bottom_layout.addWidget(self.state_box, 1)

        self.lbl_watch = QtWidgets.QLabel("Watching for external config changes…")
        self.lbl_watch.setWordWrap(True)
        bottom_layout.addWidget(self.lbl_watch)

        root.addWidget(bottom)




    def _build_monitor_dashboard(self) -> QtWidgets.QWidget:
        """Legacy wrapper for GUI.dashboard.build_dashboard."""
        return build_dashboard(self, _dot)


    def _build_config_editor_view(self) -> QtWidgets.QWidget:
        """Legacy wrapper for GUI.config_editor.build_config_editor."""
        widget = build_config_editor(self)
        JsonHL(self.json.document())
        return widget

    def _register_view(
        self,
        view_id: str,
        widget: QtWidgets.QWidget,
        on_show: Callable[[], None] | None = None,
    ) -> None:
        if self.content_stack.indexOf(widget) < 0:
            self.content_stack.addWidget(widget)
        self._view_routes[view_id] = (widget, on_show)

    def _on_view_selected(self, view_id: str):
        target = getattr(self, "_view_routes", {}).get(view_id)
        if not target:
            return
        widget, callback = target
        idx = self.content_stack.indexOf(widget)
        if idx >= 0:
            self.content_stack.setCurrentIndex(idx)
        if callback:
            callback()

    def _ensure_tab_visible(self, tab_name: str):
        if tab_name == self._search_tab_name:
            self.config_renderer.ensure_search_tab()
        idx = self._tab_index(tab_name)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
    # ----------------------------- Signals ------------------------------------
    def _signals(self):
        self.b_cfgdir.clicked.connect(self.pick_cfg_dir)
        self.b_reload_cfgs.clicked.connect(self.refresh_cfgs)
        self.cb_cfg.currentTextChanged.connect(self._cfg_selected)

        self.b_reload.clicked.connect(self.load_config_text)
        self.b_save.clicked.connect(self.save_atomic)
        self.b_validate.clicked.connect(self.validate_config)

        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(120)
        self.filter.textChanged.connect(lambda _: (timer.stop(), timer.start()))
        timer.timeout.connect(
            lambda: self.config_renderer.apply_filter(self.filter.text())
        )

        self.b_clearfilter.clicked.connect(lambda: self.filter.setText(""))
        self.b_clearlog.clicked.connect(self._clear_current_log)
        self.chk_live.toggled.connect(self._retail)
        self.btn_log_src_refresh.clicked.connect(self._populate_log_sources)
        self.btn_log_search.clicked.connect(self._run_log_search)
        self.btn_log_search_clear.clicked.connect(self._clear_log_search)
        self.cmb_mgmt_log_subsystem.currentIndexChanged.connect(
            lambda _: self._refresh_mgmt_log_files()
        )
        self.btn_mgmt_log_refresh.clicked.connect(self._populate_log_sources)
        self.btn_mgmt_log_load.clicked.connect(self._load_mgmt_log_file)
        self.btn_mgmt_log_open.clicked.connect(self._open_selected_mgmt_folder)
        self.btn_mgmt_archive.clicked.connect(self._archive_logs_now)
        self.cmb_mgmt_log_file.currentIndexChanged.connect(
            lambda _: self._load_mgmt_log_file(auto=True)
        )
        self.btn_error_refresh.clicked.connect(self._refresh_error_events)
        self.tbl_error_events.itemDoubleClicked.connect(self._open_error_log_from_table)

        self.btn_logs.clicked.connect(
            lambda: self._open_folder(self._resolved_paths()["log_file"].parent)
        )
        self.btn_rt.clicked.connect(
            lambda: self._open_folder(_runtime_paths(self.config_path)["runtime_dir"])
        )
        self.btn_bak.clicked.connect(
            lambda: self._open_folder(_runtime_paths(self.config_path)["backup_root"])
        )
        self.btn_ctl.clicked.connect(lambda: self._open_folder(CTRL_DIR))
        self.btn_adv.clicked.connect(self._open_advanced)
        self.btnBkNow.clicked.connect(self._on_backup_now_clicked)
        self.btnBkOpen.clicked.connect(self._on_open_backups_clicked)

        self.b_start.clicked.connect(self.start_server)
        self.b_stop.clicked.connect(self.stop_server)
        self.b_restart.clicked.connect(self.restart_server)
        self.b_lm_on.clicked.connect(self.start_lm)
        self.b_lm_off.clicked.connect(self.stop_lm)
        self.b_cm_on.clicked.connect(self.start_cm)
        self.b_cm_off.clicked.connect(self.stop_cm)

    # -------------------------- Config folder ---------------------------------
    def pick_cfg_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Config Folder",
            self.ed_cfgdir.text().strip() or str(CONFIG_DIR),
        )
        if d:
            self.ed_cfgdir.setText(d)
            self.config_dir = d
            self.refresh_cfgs()

    def refresh_cfgs(self):
        folder = Path(self.ed_cfgdir.text().strip() or self.config_dir)
        files = []
        self.cb_cfg.blockSignals(True)
        self.cb_cfg.clear()
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
        if not name:
            return
        self.config_path = str(Path(self.ed_cfgdir.text().strip()).joinpath(name))
        self.load_config_text()
        self.watch_config()

    # -------------------------- Tab Helpers ---------------------------------
    def _strip_cnt(self, s: str) -> str:
        # "Monitor (3)" -> "Monitor"
        return re.sub(r"\s+\(\d+\)$", "", s or "")

    def _rebuild_base_titles(self):
        self._tab_base_titles = {
            i: self._strip_cnt(self.tabs.tabText(i)) for i in range(self.tabs.count())
        }
        self._tab_index_to_name = dict(self._tab_base_titles)

    def _tab_index(self, name: str) -> int:
        base = name or ""
        for i in range(self.tabs.count()):
            if self._strip_cnt(self.tabs.tabText(i)) == base:
                return i
        return -1

    def _set_tab_count(self, name: str, count: int) -> None:
        idx = self._tab_index(name)
        if idx < 0:
            return
        base = self._strip_cnt(self.tabs.tabText(idx))
        self.tabs.setTabText(idx, base if count <= 0 else f"{base} ({count})")

    # --- backup Button helpers -------------------------------------------------
    def _on_backup_now_clicked(self):
        try:
            # make the active config path visible to Tools.backups
            os.environ["VEIN_CONFIG"] = self.config_path

            from Tools.backups import make_backup, BackupError, BackupSkip

            path = make_backup("Manual")
            self._status(f"Backup created: {getattr(path, 'name', str(path))}")
        except BackupSkip as e:
            self._status(f"Backup skipped: {e}")
        except BackupError as e:
            self._status(f"Backup failed: {e}")
        except Exception as e:
            self._status(f"Backup failed: {e}")

    def _on_open_backups_clicked(self):
        root = getattr(self, "_bk_root", None)
        if not root:
            # Fallback to current config if state is missing
            try:
                cfg, _, _ = _load_any_config(self.config_path)
                b = (cfg.get("backups", {}) or {}) if isinstance(cfg, dict) else {}
                root = b.get("root")
            except Exception:
                root = None
        if not root:
            self._status("Backups folder not found.")
            return
        try:
            QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(root)))
        except Exception:
            self._status("Failed to open backups folder.")

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
            self._hl = (
                YamlHL(self.json.document())
                if kind == "yaml"
                else JsonHL(self.json.document())
            )
            self.json.blockSignals(False)
            self.config_renderer.build_tabs(self._data)

            # Show version in status/title (with fallback)
            try:
                ver = getattr(self, "_cfg_version", None)
                if ver is None:
                    if isinstance(self._yaml_doc, dict) and "version" in self._yaml_doc:
                        ver = self._yaml_doc.get("version")
                    elif isinstance(self._data, dict) and "version" in self._data:
                        ver = self._data.get("version")

                if ver is not None:
                    self._status(f"Loaded {kind.upper()} (Config v{ver}).")
                    try:
                        self.setWindowTitle(f"Vein Server Manager - Config v{ver}")
                    except Exception:
                        pass
                else:
                    self._status(f"Loaded {kind.upper()}.")
            except Exception:
                self._status(f"Loaded {kind.upper()}.")

            self._rebuild_base_titles()
        except Exception as e:
            self._data = {}
            self.json.setPlainText("")
            self._status(f"Load error: {e}")

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
                if not _HAVE_RUAMEL:
                    raise RuntimeError("ruamel.yaml not installed")
                y = YAML()
                y.preserve_quotes = True
                y.load(self.json.toPlainText())
            else:
                import json as _json

                _json.loads(self.json.toPlainText())
            self._status("Config parses ✅")
        except Exception as e:
            self._status(f"Parse error: {e}")

    def _read_cfg_root_for_backups(self):
        try:
            cfg, _, _ = _load_any_config(self.config_path)
            b = cfg.get("backups", {}) or {}
            root = b.get("root") or b.get("paths", {}).get("root") or None
            return Path(root) if root else None
        except Exception:
            return None

    def _read_cfg_root_for_backups(self):
        try:
            cfg, _, _ = _load_any_config(self.config_path)
            b = cfg.get("backups", {}) or {}
            root = b.get("root") or b.get("paths", {}).get("root") or None
            return Path(root) if root else None
        except Exception:
            return None

    def _bump_version_in_yaml_doc(self):
        try:
            if self._cfg_kind != "yaml" or self._yaml_doc is None:
                return
            y = self._yaml_doc
            if "version" in y:
                s = str(y["version"]).strip()
                parts = s.split(".")
                if len(parts) == 1:
                    y["version"] = f"{parts[0]}.1"
                else:
                    major = parts[0]
                    try:
                        minor = int(parts[1]) + 1
                    except Exception:
                        minor = 1
                    y["version"] = f"{major}.{minor}"
        except Exception:
            pass

    def save_atomic(self):
        """Save safely, make a timestamped backup, and (optionally) bump version."""
        try:
            path = Path(self.config_path)

            # 0) Backup current file first
            if path.exists():
                bk_root = (
                    self._read_cfg_root_for_backups()
                    or Path(__file__).resolve().parents[1] / "Backups"
                )
                (bk_root / "Configs").mkdir(parents=True, exist_ok=True)
                ts = QtCore.QDateTime.currentDateTimeUtc().toString(
                    "yyyy-MM-ddThh-mm-ss-zzz'Z'"
                )
                backup_path = bk_root / "Configs" / f"{path.stem}-{ts}{path.suffix}"
                try:
                    backup_path.write_text(
                        path.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                except Exception:
                    pass

            # 1) Optional version bump (toggle lives in your config; adjust path if needed)
            try:
                cfg, kind, ydoc = _load_any_config(self.config_path)
                auto_bump = False
                try:
                    auto_bump = bool(
                        (cfg.get("lifecycle", {}) or {}).get("auto_bump_version", False)
                    )
                except Exception:
                    auto_bump = False

                if (
                    auto_bump
                    and self._cfg_kind == "yaml"
                    and self._yaml_doc is not None
                ):
                    if not hasattr(self, "_yaml_doc") or self._yaml_doc is None:
                        self._status("Config saved (no version bump: legacy format).")
                        return
                    self._bump_version_in_yaml_doc()
                    # mirror updated YAML into editor
                    self.json.blockSignals(True)
                    self.json.setPlainText(
                        _dump_any_config(self._data, "yaml", ydoc=self._yaml_doc)
                    )
                    self.json.blockSignals(False)
            except Exception:
                pass

            # 2) Atomic write
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
                    try:
                        self.watcher.removePath(p)
                    except Exception:
                        pass
            self.watcher = QtCore.QFileSystemWatcher(self)
            if Path(self.config_path).exists():
                self.watcher.addPath(self.config_path)
            self.watcher.fileChanged.connect(
                lambda _: (self._saving and None)
                or QtCore.QTimer.singleShot(300, self.load_config_text)
            )
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

        # Management logs (stdout files) - follow newest per-subsystem log
        lm_provider = lambda: mgmt_logs.latest_log_path("monitor_log", "stdout")
        cm_provider = lambda: mgmt_logs.latest_log_path("crash_monitor", "stdout")

        self.tail_lm = FileTail(lm_provider)
        self.tail_lm.chunk.connect(self._on_lm_line)
        self.tail_lm.start()

        self.tail_cm = FileTail(cm_provider)
        self.tail_cm.chunk.connect(self._on_cm_line)
        self.tail_cm.start()

    def _populate_log_sources(self):
        subsystems = mgmt_logs.available_subsystems(include_empty=True)
        self._set_subsystem_combo(self.cmb_log_sources, subsystems, include_all=True)
        self._set_subsystem_combo(
            self.cmb_mgmt_log_subsystem, subsystems, include_all=False
        )
        self._set_subsystem_combo(
            self.cmb_error_subsystem, subsystems, include_all=True
        )
        self._refresh_mgmt_log_files()

    def _set_subsystem_combo(self, combo, subsystems, include_all: bool):
        if combo is None:
            return
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        if combo is self.cmb_mgmt_log_subsystem:
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
        query = self.ed_log_search.text().strip()
        if not query:
            self.log_search_status.setText("Enter a search query to begin.")
            return
        subs_data = self.cmb_log_sources.currentData()
        subsystems = None
        archive_only: set[str] = set()
        include_archive = self.chk_log_include_archive.isChecked()
        if subs_data == "__archive__":
            subsystems = mgmt_logs.available_subsystems(include_empty=True)
            include_archive = True
            archive_only = set(subsystems)
        elif isinstance(subs_data, str) and subs_data not in (None, "__all__", ""):
            subsystems = [subs_data]
        limit = int(self.spin_log_limit.value())
        since_expr = self.cmb_log_since.currentData()
        case_sensitive = self.chk_log_case.isChecked()
        self._log_search_running = True
        self.btn_log_search.setEnabled(False)
        self.log_search_status.setText("Searching…")
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
        self._log_search_worker = worker  # keep reference

    def _log_search_ready(self, payload: list[dict]):
        lines = [
            f"[{hit['subsystem']}] {hit['file']}:{hit['line']} {hit['text']}"
            for hit in payload
        ]
        text = "\n".join(lines) if lines else "No matches."
        self.log_search_results.setPlainText(text)
        self.log_search_status.setText(f"{len(payload)} match(es)")
        self.btn_log_search.setEnabled(True)
        self._log_search_running = False

        # allow repeated GC once done
        self._log_search_worker = None

    def _log_search_error(self, message: str):
        self.log_search_status.setText(f"Search failed: {message}")
        self.btn_log_search.setEnabled(True)
        self._log_search_running = False
        self._log_search_worker = None

    def _clear_log_search(self):
        self.log_search_results.clear()
        self.log_search_status.setText("Idle")

    def _refresh_mgmt_log_files(self):
        combo = getattr(self, "cmb_mgmt_log_file", None)
        subs_combo = getattr(self, "cmb_mgmt_log_subsystem", None)
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
            self.txt_mgmt_log.setPlainText("Select a subsystem to load logs.")
            return
        else:
            files = self._collect_subsystem_files(subsystem_value)
        combo.blockSignals(False)
        if files:
            combo.setCurrentIndex(0)
            self._load_mgmt_log_file(auto=True)
        else:
            self.txt_mgmt_log.setPlainText("No logs found for this selection.")

    def _collect_subsystem_files(self, subsystem: str) -> list[tuple[Path, str]]:
        entries: list[tuple[Path, str]] = []
        for path in mgmt_logs.iter_log_files(subsystem, include_archive=False):
            if len(entries) >= 20:
                break
            try:
                ts = path.stat().st_mtime
            except Exception:
                ts = 0.0
            label = f"{path.name} ({self._format_timestamp(ts)})"
            entries.append((path, label))
        return entries

    def _collect_archive_files(self) -> list[tuple[Path, str]]:
        records: list[tuple[Path, float, str]] = []
        subsystems = mgmt_logs.available_subsystems(include_empty=True)
        for subsystem in subsystems:
            for path in mgmt_logs.iter_log_files(subsystem, include_archive=True):
                if not mgmt_logs.is_archived_path(path):
                    continue
                try:
                    ts = path.stat().st_mtime
                except Exception:
                    ts = 0.0
                label = f"[Archive/{subsystem}] {path.name} ({self._format_timestamp(ts)})"
                records.append((path, ts, label))
        records.sort(key=lambda item: item[1], reverse=True)
        return [(path, label) for path, _, label in records[:20]]

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

    def _archive_logs_now(self):
        if self._archiving_logs:
            return
        self._archiving_logs = True
        self.btn_mgmt_archive.setEnabled(False)
        self._status("Archiving logs…")
        worker = ArchiveLogsWorker()
        worker.signals.ready.connect(self._archive_logs_done)
        worker.signals.error.connect(self._archive_logs_error)
        self._pool.start(worker)
        self._archive_worker = worker

    def _archive_logs_done(self, moved: list[tuple[Path, Path]]):
        self._archiving_logs = False
        self.btn_mgmt_archive.setEnabled(True)
        self._populate_log_sources()
        count = len(moved)
        self._status(f"Archived {count} log(s).")
        self._archive_worker = None

    def _archive_logs_error(self, message: str):
        self._archiving_logs = False
        self.btn_mgmt_archive.setEnabled(True)
        self._status(f"Archive failed: {message}")
        self._archive_worker = None

    def _current_mgmt_log_file(self) -> Optional[Path]:
        combo = getattr(self, "cmb_mgmt_log_file", None)
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
                self.txt_mgmt_log.setPlainText("No log file selected.")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.txt_mgmt_log.setPlainText(text)
            if highlight_line:
                self._highlight_log_line(highlight_line, highlight_level)
            else:
                self.txt_mgmt_log.setExtraSelections([])
        except Exception as exc:
            if not auto:
                self.txt_mgmt_log.setPlainText(f"Failed to load log: {exc}")

    def _open_selected_mgmt_folder(self):
        path = self._current_mgmt_log_file()
        if path:
            self._open_folder(path.parent)

    def _format_timestamp(self, ts: float) -> str:
        if not ts:
            return "unknown"
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "unknown"

    def _refresh_error_events(self):
        if self._error_refresh_running:
            return
        subs_data = self.cmb_error_subsystem.currentData()
        subsystems = None
        archive_only = False
        include_archive = self.chk_error_include_archive.isChecked()
        if subs_data == "__archive__":
            subsystems = mgmt_logs.available_subsystems(include_empty=True)
            include_archive = True
            archive_only = True
        elif subs_data not in (None, "__all__", ""):
            subsystems = [subs_data]
        since_expr = self.cmb_error_since.currentData()
        limit = int(self.spin_error_limit.value())
        self._error_refresh_running = True
        self.btn_error_refresh.setEnabled(False)
        self.lbl_error_status.setText("Scanning errors.")
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
        table = self.tbl_error_events
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
            status += f" • newest {self._format_timestamp(latest_ts)}"
        self.lbl_error_status.setText(status)
        self.btn_error_refresh.setEnabled(True)
        self._error_refresh_running = False
        self._error_worker = None

    def _error_error(self, message: str):
        self.lbl_error_status.setText(f"Error summary failed: {message}")
        self.btn_error_refresh.setEnabled(True)
        self._error_refresh_running = False
        self._error_worker = None

    def _open_error_log_from_table(self, item):
        row = item.row()
        data_item = self.tbl_error_events.item(row, 2)
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

    def _ensure_subsystem_selected(self, subsystem: str, archived: bool = False) -> None:
        combo = self.cmb_mgmt_log_subsystem
        if not combo or not subsystem:
            return
        value = f"archive::{subsystem}" if archived else subsystem
        display = f"Archive: {subsystem}" if archived else subsystem
        idx = combo.findData(value)
        if idx < 0:
            combo.addItem(display, value)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _select_mgmt_log_file(self, path: Path) -> None:
        combo = self.cmb_mgmt_log_file
        if not combo:
            return
        data = str(path)
        idx = combo.findData(data)
        if idx < 0:
            label = path.name
            if mgmt_logs.is_archived_path(path):
                subsystem = self._infer_subsystem_from_path(path)
                label = f"[Archive/{subsystem}] {label}"
            combo.addItem(label, data)
            idx = combo.count() - 1
        combo.setCurrentIndex(idx)

    def _load_log_into_subsystem_tab(
        self,
        rel_path: str,
        line: int,
        *,
        subsystem: str | None = None,
        level: str | None = None,
    ):
        if not rel_path:
            return
        root = mgmt_logs.management_log_root()
        path = root / rel_path
        archived = mgmt_logs.is_archived_path(path)
        if subsystem is None:
            subsystem = self._infer_subsystem_from_path(path)
        if subsystem:
            self._ensure_subsystem_selected(subsystem, archived=archived)
        if not path.exists():
            self.txt_mgmt_log.setPlainText(f"Log not found: {path}")
            self.logTabs.setCurrentWidget(self.mgmt_log_tab)
            return
        self._select_mgmt_log_file(path)
        self._load_mgmt_log_file(
            auto=True, highlight_line=line, highlight_level=level
        )
        self.logTabs.setCurrentWidget(self.mgmt_log_tab)

    def _highlight_log_line(self, line: int, level: Optional[str]):
        cursor = self.txt_mgmt_log.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        for _ in range(max(0, line - 1)):
            if not cursor.movePosition(QtGui.QTextCursor.Down):
                break
        selection_cursor = QtGui.QTextCursor(cursor)
        selection_cursor.movePosition(QtGui.QTextCursor.EndOfLine, QtGui.QTextCursor.KeepAnchor)
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.cursor = selection_cursor
        fmt = QtGui.QTextCharFormat()
        color = self._highlight_color_for_level(level)
        fmt.setBackground(QtGui.QColor(color))
        fmt.setForeground(QtGui.QColor("#000000"))
        selection.format = fmt
        self.txt_mgmt_log.setExtraSelections([selection])
        cursor.setPosition(selection_cursor.anchor())
        self.txt_mgmt_log.setTextCursor(cursor)
        self.txt_mgmt_log.ensureCursorVisible()

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
        flush_buf(self._buf_lm, self.log_lm)
        flush_buf(self._buf_cm, self.log_cm)

    # ------------------------ Server / monitors -------------------------------
    def _resolved_paths(self) -> Dict[str, Path]:
        ov = {} if self.use_defaults else self.overrides
        return _resolved_paths(self.config_path, ov)

    def start_server(self):
        paths = self._resolved_paths()
        py = paths["start_server"]
        if not py.exists():
            self._status("start_server.py not found.")
            return
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.config_path
        srv_stdout = mgmt_logs.allocate_log_file(
            "vein_manager",
            label="start_server",
            record_latest=False,
            metadata={"action": "start_server", "config": self.config_path},
        )
        try:
            spawn_logged(f'{_pyexe()} "{py}"', srv_stdout, py.parent, env=env)
            self._status("Server starting…")
        except Exception as e:
            self._status(f"Start failed: {e}")

    def stop_server(self):
        paths = self._resolved_paths()
        py = paths["shutdown_server"]
        if not py.exists():
            self._status("shutdown_server.py not found.")
            return
        try:
            code, out, err = run_once(f'{_pyexe()} "{py}"', cwd=py.parent, timeout=180)
            if out:
                self._write_action_log("stop_server", "stdout", out)
            if err:
                self._write_action_log("stop_server", "stderr", err)
            self._status(
                "Server stop requested."
                if code == 0
                else f"Stop returned {code}. {err or out}"
            )
        except Exception as e:
            self._status(f"Stop failed: {e}")

    def restart_server(self):
        self.stop_server()
        QtCore.QTimer.singleShot(1200, self.start_server)

    def start_lm(self):
        paths = self._resolved_paths()
        mon_py = paths["monitor_log"]
        if not mon_py.exists():
            self._status("monitor_log.py not found.")
            return
        rp = _rt_paths(self.config_path)
        _rm(rp["stop_log"])
        _rm(rp["pid_log"])
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.config_path

        # Write monitor stdout/stderr here:
        lm_stdout = mgmt_logs.allocate_log_file(
            "monitor_log",
            label="monitor_log",
            metadata={"action": "start_monitor_log"},
        )
        try:
            spawn_logged(
                f'{_pyexe()} "{mon_py}" --follow', lm_stdout, mon_py.parent, env=env
            )
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
                    f"{_pyexe()} -c \"import sys;sys.path.insert(0, r'{CTRL_DIR}');from Tools import monitors;monitors.stop_log_monitor();print('OK')\"",
                    CTRL_DIR,
                    timeout=10,
                )
            except Exception:
                pass
            if not _wait_for_monitor_exit(rp["pid_log"], timeout_sec=10):
                # last resort: force-kill by command line match
                try:
                    run_once(
                        'powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | '
                        "Where-Object { $_.CommandLine -match 'monitor_log.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }\"",
                        timeout=8,
                    )
                except Exception:
                    pass
            self._status("Log Monitor stop requested.")

    def start_cm(self):
        paths = self._resolved_paths()
        cm_py = paths["crash_monitor"]
        if not cm_py.exists():
            self._status("crash_monitor.py not found.")
            return
        rp = _rt_paths(self.config_path)
        _rm(rp["stop_crash"])
        _rm(rp["pid_crash"])
        env = os.environ.copy()
        env["VEIN_CONFIG"] = self.config_path

        cm_stdout = mgmt_logs.allocate_log_file(
            "crash_monitor",
            label="crash_monitor",
            metadata={"action": "start_crash_monitor"},
        )
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
                    f"{_pyexe()} -c \"import sys;sys.path.insert(0, r'{CTRL_DIR}');from Tools import monitors;monitors.stop_crash_monitor();print('OK')\"",
                    CTRL_DIR,
                    timeout=10,
                )
            except Exception:
                pass
            if not _wait_for_monitor_exit(rp["pid_crash"], timeout_sec=10):
                try:
                    run_once(
                        'powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process | '
                        "Where-Object { $_.CommandLine -match 'crash_monitor.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }\"",
                        timeout=8,
                    )
                except Exception:
                    pass
            self._status("Crash Monitor stop requested.")

    # ----------------------- Background status wiring -------------------------
    def _apply_status_snapshot(self, snap: dict):
        # Update gumballs without blocking
        def dot(on, warn=False):
            return _dot(on, warn)

        # Server
        self.dot_srv.setStyleSheet(dot(snap.get("server", False)))
        # Log monitor: green if alive+fresh; yellow if alive but stale
        lm_on = snap.get("logmon", False)
        lm_fresh = snap.get("logmon_fresh", False)
        self.dot_lm.setStyleSheet(
            dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh))
        )
        # Crash monitor
        cm_on = snap.get("crashmon", False)
        self.dot_cm.setStyleSheet(dot(cm_on))
        cmode = snap.get("crash_mode", "unknown")
        self.lblCrashMode.setText(cmode)
        self.b_cm_on.setToolTip(f"Crash monitor mode: {cmode}")
        self.b_cm_off.setToolTip(f"Crash monitor mode: {cmode}")

        # Dashboard detail (read server_state only once here)
        rp = _runtime_paths(self.config_path)
        rt = _rt_paths(self.config_path)
        st = self._safe_json(rp["server_state"])
        lms = self._safe_json(rt["state_log"])
        last = lms.get("last_updated") if lms else None
        self.lblLogDot.setStyleSheet(
            dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh))
        )
        self.lblLogStatus.setText("running" if lm_on else "stopped")
        self.lblLogLast.setText(f"Last update: {_age_str(last)}")
        self.lblLogJoin.setText(f"Joinable: {st.get('server_joinable') if st else '—'}")
        self.lblLogPlayers.setText(f"Players: {st.get('player_count') if st else '—'}")
        if st and isinstance(st.get("uptime_seconds"), int):
            up = st["uptime_seconds"]
            self.lblLogUptime.setText(
                f"Uptime: {up//3600:02d}:{(up%3600)//60:02d}:{up%60:02d}"
            )
        else:
            self.lblLogUptime.setText("Uptime: —")

        http_state = lms.get("http_api") if isinstance(lms, dict) else None

        self._update_http_api_summary(http_state)
        player_snapshot = {}
        snap_path = rt.get("player_snapshot")
        if snap_path:
            player_snapshot = self._safe_json(snap_path)
        self._render_player_tree(player_snapshot)

        # Hint the tailer in case path switched (next poll will re-open)
        if self.tail_game:
            try:
                _ = (
                    self._current_game_log_path()
                )  # will be read by provider on next poll
            except Exception:
                pass

        cs = self._safe_json(rp["crash_state"])
        self.lblCrashDot.setStyleSheet(dot(cm_on))
        self.lblCrashLast.setText(f"Last heartbeat: {_age_str(cs.get('ts'))}")

        bk = snap.get("backup", {}) or {}
        bk_last = bk.get("last_utc") or "—"
        bk_file = bk.get("last_zip") or "—"
        bk_total = (bk.get("counts") or {}).get("TOTAL", 0)

        # --- Backups card update ---
        bk_enabled = bool((snap.get("backup") or {}).get("enabled", True))
        bk_counts = (snap.get("backup") or {}).get("counts") or {}
        age = _age_str(bk_last) if bk_last and bk_last != "—" else "—"

        def _fmt_counts(d: dict) -> str:
            if not d:
                return "—"
            keys = [k for k in d.keys() if k != "TOTAL"]
            keys.sort()
            return "  ".join(
                [*(f"{k}={d.get(k,0)}" for k in keys), f"TOTAL={d.get('TOTAL',0)}"]
            )

        self.lblBkEnabled.setText("ON" if bk_enabled else "OFF")
        self.lblBkLast.setText(bk_last)
        self.lblBkFile.setText(bk_file)
        self.lblBkTotal.setText(str(bk_total))
        self.lblBkCounts.setText(_fmt_counts(bk_counts))
        self.btnBkNow.setEnabled(bk_enabled)
        self.lblBkLast.setText(f"{bk_last}  ({age})")

        # Save root for the open handler
        self._bk_root = (snap.get("backup") or {}).get("root")

        # Extend the compact state line
        self.state_box.setText(
            f"Server flag: {'present' if _file_exists(rp['state_flag']) else 'absent'}   |   "
            f"Shutdown flag: {'present' if _file_exists(rp['shutdown_flag']) else 'absent'}   |   "
            f"Backup: Last={bk_last} • File={bk_file} • Total={bk_total}"
        )

        # Nice UX touch: show details on the “Open Backups” button
        try:
            self.btn_bak.setToolTip(
                f"Last backup: {bk_last}\nFile: {bk_file}\nTotal archives: {bk_total}"
            )
        except Exception:
            pass

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

    def _update_http_api_summary(self, http_state: Optional[dict]) -> None:
        if not hasattr(self, "lblLogHttpStatus"):
            return

        status_text = "HTTP API: disabled"
        players_text = "API Players: —"
        world_text = "World Time: —"
        weather_text = "Weather: —"

        if isinstance(http_state, dict):
            enabled = bool(http_state.get("enabled", False))
            last_fetch = http_state.get("last_fetch")
            errors = http_state.get("errors") or []

            if not enabled:
                err = http_state.get("last_error") or (errors[0] if errors else "")
                status_text = f"HTTP API: disabled{f' ({err})' if err else ''}"
            else:
                if last_fetch:
                    status_text = f"HTTP API: OK (last {_age_str(last_fetch)} ago)"
                else:
                    status_text = "HTTP API: enabled (waiting for first fetch)"
                if errors:
                    status_text += f" | Last error: {errors[0]}"
                players_text = self._format_http_api_players(http_state)
                world_text = self._format_http_api_time(
                    http_state.get("time"), http_state.get("status")
                )
                weather_text = self._format_http_api_weather(
                    http_state.get("weather")
                )

        self.lblLogHttpStatus.setText(status_text)
        self.lblLogHttpPlayers.setText(players_text)
        self.lblLogHttpWorld.setText(world_text)
        self.lblLogHttpWeather.setText(weather_text)

    def _render_player_tree(self, snapshot: Optional[dict]) -> None:
        if not hasattr(self, "playerTree"):
            return
        data = snapshot or {}
        self._player_snapshot_raw = data
        cache_entries = self._update_player_cache(data)

        admins = data.get("admins") or []
        if admins:
            admin_text = ", ".join(
                f"{(a.get('name') or a.get('steam_id') or '').strip()} ({a.get('steam_id')})"
                for a in admins
                if a
            )
            self.lblAdminList.setText(f"Admins online: {admin_text}")
        else:
            configured = self._configured_admin_ids()
            if configured:
                self.lblAdminList.setText(
                    "Admins (configured): " + ", ".join(configured)
                )
            else:
                self.lblAdminList.setText("Admins: none configured")

        ts = data.get("last_updated")
        if ts:
            age = _age_str(ts)
            self.lblPlayerSnapshotTs.setText(f"Players refreshed: {age} ago")
        else:
            self.lblPlayerSnapshotTs.setText("Players refreshed: �")

        errors = data.get("errors") or []
        if errors:
            self.lblPlayerErrors.setText("HTTP errors: " + "; ".join(errors[:3]))
        else:
            self.lblPlayerErrors.setText("")

        signature = tuple(
            (
                entry.get("steam_id"),
                entry.get("online"),
                entry.get("in_character_select"),
                 entry.get("online_state"),
                 entry.get("verified_by_api"),
                 entry.get("last_log_event"),
                 entry.get("last_http_event"),
                entry.get("current_character_id"),
                tuple(
                    (char.get("character_id"), char.get("name"))
                    for char in entry.get("characters") or []
                ),
            )
            for entry in cache_entries
        )
        if signature == self._player_tree_signature:
            return
        self._player_tree_signature = signature

        state = self._capture_player_tree_state()
        self.playerTree.clear()
        if not cache_entries:
            placeholder = QtWidgets.QTreeWidgetItem(["No recent players", "", ""])
            placeholder.setDisabled(True)
            self.playerTree.addTopLevelItem(placeholder)
            return

        for entry in cache_entries:
            steam_id = entry.get("steam_id") or "?"
            name = entry.get("name") or steam_id
            online = entry.get("online", False)
            in_select = entry.get("in_character_select", False)
            current_char_id = entry.get("current_character_id")
            online_state = entry.get("online_state") or (
                "online" if online else "offline"
            )

            display = name + ("" if online else " (offline)")
            status_text = (entry.get("status") or "").strip()
            detail_bits: list[str] = []
            if online and in_select:
                detail_bits.append("state: character select")
                icon = self._status_icon("select", "#E67E22")
            elif online:
                detail_bits.append(f"state: {status_text or online_state}")
                icon = self._status_icon("online", "#2ECC71")
            else:
                last_seen = entry.get("last_online") or entry.get("last_seen")
                if last_seen:
                    detail_bits.append(f"last online {_age_str(last_seen)} ago")
                else:
                    detail_bits.append("offline")
                icon = self._status_icon("offline", "#E74C3C")
            if entry.get("verified_by_api"):
                detail_bits.append("API ✔")
            elif online:
                detail_bits.append("log-only")
            last_log = entry.get("last_log_event")
            if last_log:
                detail_bits.append(f"log {_age_str(last_log)} ago")
            last_http = entry.get("last_http_event")
            if last_http:
                detail_bits.append(f"HTTP {_age_str(last_http)} ago")
            detail = " | ".join(detail_bits)
            if current_char_id and online and not in_select:
                current_char_name = self._find_character_name(entry, current_char_id)
                if current_char_name:
                    detail += f" — playing {current_char_name}"
            player_payload = {"type": "player", "data": entry, "key": f"player:{steam_id}"}
            top = QtWidgets.QTreeWidgetItem([display, steam_id, detail])
            if icon:
                top.setIcon(0, icon)
            top.setData(0, QtCore.Qt.UserRole, player_payload)
            if not online:
                gray = QtGui.QBrush(QtGui.QColor("#95A5A6"))
                top.setForeground(0, gray)
                top.setForeground(1, gray)
                top.setForeground(2, gray)

            for char in entry.get("characters") or []:
                char_id = char.get("character_id") or "?"
                char_name = char.get("name") or char_id
                summary = self._summarize_character(char) or "double-click for inventory"
                char_payload = {
                    "type": "character",
                    "data": char,
                    "key": f"char:{steam_id}:{char_id}",
                }
                char_label = char_name
                if current_char_id and char_id == current_char_id and online and not in_select:
                    char_label = f"{char_name} (active)"
                child = QtWidgets.QTreeWidgetItem([char_label, char_id, summary])
                child.setData(0, QtCore.Qt.UserRole, char_payload)
                if not online:
                    gray = QtGui.QBrush(QtGui.QColor("#95A5A6"))
                    child.setForeground(0, gray)
                    child.setForeground(1, gray)
                    child.setForeground(2, gray)
                top.addChild(child)
            self.playerTree.addTopLevelItem(top)
        self._restore_player_tree_state(state)

    def _summarize_character(self, entry: dict) -> str:
        data = entry.get("data") or {}
        char_data = data.get("characterData") or {}
        pieces: list[str] = []
        if isinstance(char_data, dict):
            level = char_data.get("level") or char_data.get("Level")
            if level is not None:
                pieces.append(f"level {level}")
            hp = char_data.get("health") or char_data.get("Health")
            if hp is not None:
                pieces.append(f"HP {hp}")
        inventory = data.get("inventory")
        if isinstance(inventory, dict):
            items = inventory.get("items") or inventory.get("Entries")
            if isinstance(items, list):
                pieces.append(f"{len(items)} items")
        return ", ".join(pieces)

    def _find_character_name(self, entry: dict, char_id: str) -> Optional[str]:
        for char in entry.get("characters") or []:
            if str(char.get("character_id")) == str(char_id):
                return char.get("name") or str(char_id)
        return None

    def _status_icon(self, key: str, color: str) -> QtGui.QIcon:
        cache_key = (key, color)
        icon = self._status_icon_cache.get(cache_key)
        if icon:
            return icon
        pix = QtGui.QPixmap(12, 12)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(color)))
        painter.setPen(QtGui.QPen(QtGui.QColor(color)))
        painter.drawEllipse(0, 0, 12, 12)
        painter.end()
        icon = QtGui.QIcon(pix)
        self._status_icon_cache[cache_key] = icon
        return icon

    def _format_http_api_players(self, http_state: dict) -> str:
        status_payload = http_state.get("status") or {}
        players_payload = http_state.get("players") or {}
        names: list[str] = []
        online_reported = False

        online = status_payload.get("onlinePlayers")
        if isinstance(online, dict):
            online_reported = True
            for sid, pdata in online.items():
                name = None
                if isinstance(pdata, dict):
                    name = (pdata.get("name") or pdata.get("characterId") or "").strip()
                alias = name or str(sid)
                if alias:
                    names.append(alias)
            if not names:
                return "API Players: 0"

        if not online_reported:
            player_ids = players_payload.get("players")
            if isinstance(player_ids, list):
                names = [str(pid) for pid in player_ids]

        if not names:
            return "API Players: 0"

        count = len(names)
        preview = ", ".join(names[:4])
        if count > 4:
            preview += f", +{count - 4} more"
        return f"API Players: {count} ({preview})"
    def _format_http_api_time(
        self, time_payload: Optional[dict], status_payload: Optional[dict]
    ) -> str:
        label = "World Time: —"
        ts = (
            time_payload.get("unixSeconds")
            if isinstance(time_payload, dict)
            else None
        )
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            label = f"World Time: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC"

        uptime = (
            status_payload.get("uptime") if isinstance(status_payload, dict) else None
        )
        if isinstance(uptime, (int, float)):
            seconds = int(uptime * 3600) if uptime < 1e6 else int(uptime)
            label += f" | API Uptime: {self._format_duration(seconds)}"
        return label

    def _format_http_api_weather(self, payload: Optional[dict]) -> str:
        if not isinstance(payload, dict):
            return "Weather: —"

        parts: list[str] = []
        temp = payload.get("temperature")
        if isinstance(temp, (int, float)):
            parts.append(f"{temp:.1f}°C")

        humidity = payload.get("relativeHumidity")
        if isinstance(humidity, (int, float)):
            pct = humidity * 100 if humidity <= 1 else humidity
            parts.append(f"humidity {pct:.0f}%")

        wind_dir = payload.get("windDirection")
        wind_force = payload.get("windForce")
        if isinstance(wind_dir, (int, float)) and isinstance(wind_force, (int, float)):
            parts.append(f"wind {wind_dir:.0f}°@{wind_force:.1f}")

        precip = payload.get("precipitation")
        if isinstance(precip, (int, float)):
            parts.append(f"precip {precip:.2f}")

        if not parts:
            return "Weather: —"
        return f"Weather: {', '.join(parts)}"

    def _configured_admin_ids(self) -> List[str]:
        if self._cached_admin_ids is not None:
            return self._cached_admin_ids

        cfg = _load_cfg_for_runtime(self.config_path)
        ids: list[str] = []
        for key in ("SuperAdminSteamIDs", "AdminSteamIDs"):
            raw = cfg.get(key) or []
            if isinstance(raw, (list, tuple)):
                for entry in raw:
                    sid = str(entry).strip()
                    if sid and sid not in ids:
                        ids.append(sid)
            elif isinstance(raw, str) and raw.strip():
                sid = raw.strip()
                if sid not in ids:
                    ids.append(sid)

        self._cached_admin_ids = ids
        return ids

    def _update_player_cache(self, snapshot: Optional[dict]) -> List[dict]:
        if not hasattr(self, "_player_cache"):
            self._player_cache = {}

        players = []
        if isinstance(snapshot, dict):
            raw = snapshot.get("players")
            if isinstance(raw, list):
                players = raw
        now_iso = datetime.now(timezone.utc).isoformat()
        cache = self._player_cache
        current_ids: set[str] = set()
        for player in players:
            steam_id = str(player.get("steam_id") or "").strip()
            if not steam_id:
                continue
            current_ids.add(steam_id)
            entry = cache.get(steam_id, {})
            last_seen = player.get("last_seen") or player.get("last_online") or now_iso
            online_state = player.get("online_state")
            is_online = online_state != "offline" if online_state else bool(
                player.get("online", True)
            )
            entry.update(
                steam_id=steam_id,
                name=player.get("name") or entry.get("name") or steam_id,
                status=player.get("status"),
                last_online=last_seen,
                online=is_online,
                online_state=online_state or ("online" if is_online else "offline"),
                in_character_select=player.get("in_character_select", False),
                current_character_id=player.get("current_character_id"),
                player=player,
                characters=player.get("characters") or [],
                verified_by_api=bool(player.get("verified_by_api")),
                last_log_event=player.get("last_log_event"),
                last_http_event=player.get("last_http_event"),
                events=player.get("events") or entry.get("events") or [],
            )
            cache[steam_id] = entry

        for sid, entry in list(cache.items()):
            if sid not in current_ids:
                entry["online"] = False
                entry["online_state"] = "offline"
                entry["in_character_select"] = False
                entry.setdefault("last_online", now_iso)

        sorted_entries = sorted(
            cache.values(),
            key=lambda e: e.get("last_online") or "",
            reverse=True,
        )
        trimmed = sorted_entries[:10]
        self._player_cache = {entry["steam_id"]: entry for entry in trimmed}
        return trimmed

    def _capture_player_tree_state(self) -> dict:
        state = {"expanded": set(), "selected": None}
        tree = getattr(self, "playerTree", None)
        if not tree:
            return state

        def walk(item):
            if item is None:
                return
            payload = item.data(0, QtCore.Qt.UserRole) or {}
            key = payload.get("key")
            if item.isExpanded() and key:
                state["expanded"].add(key)
            if item.isSelected() and key:
                state["selected"] = key
            for idx in range(item.childCount()):
                walk(item.child(idx))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return state

    def _restore_player_tree_state(self, state: dict) -> None:
        tree = getattr(self, "playerTree", None)
        if not tree or not state:
            return
        expanded = state.get("expanded") or set()
        selected_key = state.get("selected")

        def walk(item):
            if item is None:
                return
            payload = item.data(0, QtCore.Qt.UserRole) or {}
            key = payload.get("key")
            if key in expanded:
                item.setExpanded(True)
            if selected_key and key == selected_key:
                item.setSelected(True)
                tree.setCurrentItem(item)
            for idx in range(item.childCount()):
                walk(item.child(idx))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))

    def _format_duration(self, seconds: int) -> str:
        seconds = max(0, int(seconds))
        return f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"

    def _kick_status_poll(self):
        worker = StatusPoller(self.config_path, _load_any_config)
        worker.signals.ready.connect(self._apply_status_snapshot)
        self._pool.start(worker)

    # ------------------------------- Misc -------------------------------------
    def _safe_json(self, p: Path) -> dict:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _row_matched(self, r: "KVRow") -> bool:
        return bool(getattr(r, "_match", False))

    def _status(self, s: str):
        self.status.setText(f"Status: {s}")

    def _open_folder(self, p: Path):
        if not p:
            return
        try:
            os.startfile(str(p))  # Windows
        except Exception:
            pass

    def _write_action_log(self, action: str, stream: str, payload: str) -> None:
        """Persist ad-hoc command output without clobbering main GUI logs."""
        try:
            actions_dir = mgmt_logs.subsystem_dir("vein_manager") / "actions"
            actions_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = actions_dir / f"{action}.{ts}.{stream}.log"
            path.write_text(payload, encoding="utf-8", errors="replace")
        except Exception:
            pass

    def _open_advanced(self):
        dlg = AdvancedDialog(self.config_path, parent=self)
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
        g = q.value("main/geometry")
        st = q.value("main/state")
        if g:
            self.restoreGeometry(g)
        if st:
            self.restoreState(st)

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
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()





