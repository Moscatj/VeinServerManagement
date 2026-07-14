# vein_manager.py - Vein Server Manager (clean header + Monitors tab + Advanced Overrides)
from __future__ import annotations

# --- stdlib imports first
import json, os, sys, subprocess, time, re
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional, Callable
from datetime import datetime, timezone
import collections
import atexit

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
APP_ORG = "VeinServerManagement"
APP_NAME = "VeinManager"
# Ensure we can import Tools/* even if PYTHONPATH wasn't set by the .bat
if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))

# Now it is safe to import Tools modules
try:
    from Tools.config_io import load_and_validate_config
    from Tools import app_info, mgmt_logs
    from Tools.server_quickstart import ExistingServerSettings, inspect_server_root
except Exception as e:
    print(f"[FATAL] Could not import Tools components from {CTRL_DIR}: {e}")
    sys.exit(1)

try:
    from GUI import (
        NavigationItem,
        NavigationPanel,
        ExistingServerLoadWorker,
        apply_design_system,
        apply_quick_start,
        build_config_editor,
        build_dashboard,
        home_health_state,
        normalize_player_snapshot,
        runtime_server_joinable,
        server_action_state,
        server_runtime_labels,
        should_autostart_log_monitor,
        startup_runtime_feedback,
        build_command_bar,
        build_left_panel,
        build_log_panel,
        CollapsibleBox,
        KVRow,
        handle_player_tree_double_click,
        StatusBus,
        StatusPoller,
        PreflightWorker,
        ServerConfigEditWorker,
        ServerConfigPreviewWorker,
        build_quick_start_preview,
        build_quick_start_view,
        build_server_config_preview_view,
        ConfigRenderer,
        enforce_quick_start_root_mode,
        LogPanelController,
        ProcessController,
        populate_existing_server_settings,
        NavigationController,
        ConfigController,
        StatusRenderer,
        show_about_dialog,
        set_button_role,
        set_startup_feedback,
        set_quick_start_mode,
        update_quick_start_game_log_path,
        update_quick_start_save_games_path,
    )
except Exception as e:
    print(f"[FATAL] Could not import Controller.GUI components: {e}")
    sys.exit(1)


def _source_python_executable(
    executable: str | Path, *, windows: bool | None = None
) -> Path:
    """Return the console interpreter beside a source GUI's Python runtime."""
    path = Path(executable)
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows and path.name.lower() == "pythonw.exe":
        console_path = path.with_name("python.exe")
        if console_path.is_file():
            return console_path
    return path


def _pyexe() -> str:
    override = PYEXE_ENV.strip()
    if override:
        return override
    executable = _source_python_executable(sys.executable)
    return subprocess.list2cmdline([str(executable)])


# --- move these helpers ABOVE DEFAULT_CONFIG ---
def _is_yaml_path(p: str) -> bool:
    s = (p or "").lower()
    return s.endswith(".yaml") or s.endswith(".yml")


def _list_config_files(folder: Path) -> list[str]:
    def _is_example(path: Path) -> bool:
        name = path.name.lower()
        return "example" in name or ".sample" in name

    non_examples = []
    examples = []
    for pattern in ("*.json", "*.yaml", "*.yml"):
        for p in folder.glob(pattern):
            (examples if _is_example(p) else non_examples).append(p.name)
    return sorted(non_examples) + sorted(examples)


def first_cfg_in(folder: Path):
    cands = _list_config_files(folder)
    return (folder / cands[0]) if cands else None


# compute DEFAULT_CONFIG only after helpers exist
def _default_config_path() -> Path:
    """Prefer real configs; keep example files last."""
    env = ENV.get("VEIN_CONFIG")
    if env:
        return Path(env)
    primary = CONFIG_DIR / "config.yaml"
    if primary.exists():
        return primary
    yml = CONFIG_DIR / "config.yml"
    if yml.exists():
        return yml
    # Avoid auto-selecting example templates unless nothing else exists.
    cands = _list_config_files(CONFIG_DIR)
    for name in cands:
        if "example" not in name.lower():
            return CONFIG_DIR / name
    return CONFIG_DIR / (cands[0] if cands else "config.yaml")


DEFAULT_CONFIG = Path(_default_config_path())

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

        # Python unhandled exceptions to stderr file
        def _excepthook(tp, val, tb):
            import traceback

            traceback.print_exception(tp, val, tb, file=sys.stderr)
            sys.stderr.flush()

        sys.excepthook = _excepthook

        # Capture unraisable exceptions (background callbacks/weakrefs)
        def _unraisablehook(unraisable):
            import traceback

            try:
                sys.stderr.write("[Unraisable] ")
                if unraisable.object:
                    sys.stderr.write(f"{unraisable.object!r}: ")
                traceback.print_exception(
                    unraisable.exc_type,
                    unraisable.exc_value,
                    unraisable.exc_traceback,
                    file=sys.stderr,
                )
                sys.stderr.flush()
            except Exception:
                pass

        sys.unraisablehook = _unraisablehook

        # Qt messages to stderr file
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
            # Attempt to catch hard crashes as well
            import signal

            for sig in (getattr(signal, "SIGABRT", None), getattr(signal, "SIGSEGV", None)):
                if sig is not None:
                    try:
                        faulthandler.register(sig, file=sys.stderr, all_threads=True)
                    except Exception:
                        pass
        except Exception:
            pass

        print("[VeinManager] Process logging initialized.")
        print(f"[VeinManager] stdout: {out}")
        print(f"[VeinManager] stderr: {err}")
        sys.stdout.flush()
        sys.stderr.flush()
        atexit.register(lambda: (sys.stdout.flush(), sys.stderr.flush()))
    except Exception as e:
        # Last-ditch: don't crash if logging setup fails
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
        # Use round-trip mode here because the config editor needs to preserve
        # comments and ordering. Runtime polling paths use _load_cfg_for_runtime.
        try:
            from ruamel.yaml import YAML

            y = YAML(typ="rt", pure=True)
            y.preserve_quotes = True
            doc = y.load(txt) or {}
            data = dict(doc) if isinstance(doc, dict) else {}
            return data, "yaml", doc
        except Exception:
            pass

        # Fallback: force PyYAML pure-Python loader (avoid libyaml C extension).
        try:
            import os
            os.environ.setdefault("YAML_CYAML", "0")
            import yaml as _pyyaml
            from yaml import loader as _py_loader

            doc = _pyyaml.load(txt, Loader=_py_loader.BaseLoader) or {}
            data = dict(doc) if isinstance(doc, dict) else {}
            return data, "yaml", None
        except Exception as inner:
            sys.stderr.write(f"[Config] Failed to load YAML {p}: {inner}\n")
            sys.stderr.flush()
            return {}, "yaml", None
    else:
        import json as _json

        data = _json.loads(txt) if txt.strip() else {}
        return data, "json", None


def _dump_any_config(obj, kind: str, ydoc=None) -> str:
    from io import StringIO

    if kind == "yaml":
        if not _HAVE_RUAMEL:
            raise RuntimeError("Cannot write YAML without ruamel.yaml.")
        y = YAML(typ="rt", pure=True)
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
    rt = Path(_cfg_path_value(cfg, "runtime_dir") or RUNTIME_FALLBACK)
    monitor_cfg = cfg.get("log_monitor") or cfg.get("monitor") or {}
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
_RUNTIME_CFG_CACHE: dict[str, tuple[float | None, dict]] = {}


def _load_cfg_with_config_module(cfg_path: str) -> dict:
    import config as config_module

    path = Path(cfg_path).expanduser()
    old_env = os.environ.get("VEIN_CONFIG")
    old_cache = getattr(config_module, "_CONFIG_CACHE", None)
    try:
        os.environ["VEIN_CONFIG"] = str(path)
        if hasattr(config_module, "_CONFIG_CACHE"):
            config_module._CONFIG_CACHE = None
        loaded = config_module.load_config()
        return dict(loaded) if isinstance(loaded, dict) else {}
    finally:
        if old_env is None:
            os.environ.pop("VEIN_CONFIG", None)
        else:
            os.environ["VEIN_CONFIG"] = old_env
        if hasattr(config_module, "_CONFIG_CACHE"):
            config_module._CONFIG_CACHE = old_cache


def _load_cfg_raw_safe(cfg_path: str) -> dict:
    path = Path(cfg_path).expanduser()
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return dict(data) if isinstance(data, dict) else {}


def _load_cfg_for_runtime(cfg_path: str) -> dict:
    path = Path(cfg_path).expanduser()
    try:
        resolved = str(path.resolve())
    except Exception:
        resolved = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None

    cached = _RUNTIME_CFG_CACHE.get(resolved)
    if cached and cached[0] == mtime:
        return dict(cached[1])

    try:
        cfg = _load_cfg_with_config_module(cfg_path)
    except Exception:
        try:
            cfg = _load_cfg_raw_safe(cfg_path)
        except Exception:
            cfg = {}

    _RUNTIME_CFG_CACHE[resolved] = (mtime, dict(cfg))
    return dict(cfg)


def _cfg_section(cfg: dict, key: str) -> dict:
    value = cfg.get(key)
    return value if isinstance(value, dict) else {}


def _cfg_path_value(
    cfg: dict,
    flat_key: str,
    *,
    section: str = "paths",
    aliases: tuple[str, ...] = (),
):
    value = cfg.get(flat_key)
    if value:
        return value
    section_cfg = _cfg_section(cfg, section)
    for key in aliases or (flat_key,):
        value = section_cfg.get(key)
        if value:
            return value
    return None


def _runtime_paths(cfg_path: str) -> dict:
    cfg = _load_cfg_for_runtime(cfg_path)
    rt = Path(_cfg_path_value(cfg, "runtime_dir") or RUNTIME_FALLBACK)
    server_dir = Path(
        _cfg_path_value(cfg, "server_dir", aliases=("server_root", "server_dir"))
        or ROOT.parent
    )

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

    monitor = cfg.get("log_monitor") or cfg.get("monitor") or {}
    monitor = monitor if isinstance(monitor, dict) else {}
    game_log_cfg = cfg.get("game_log")
    uses_game_log_setting = isinstance(game_log_cfg, dict)
    game_log_override = (
        str(game_log_cfg.get("override") or "").strip()
        if uses_game_log_setting
        else str(_cfg_path_value(cfg, "absolute_log_file") or "").strip()
    )
    if game_log_override:
        resolved_game_log = Path(game_log_override)
    elif not uses_game_log_setting and _cfg_path_value(
        cfg, "logs_dir", aliases=("logs_dir", "logs")
    ):
        resolved_game_log = Path(
            _cfg_path_value(cfg, "logs_dir", aliases=("logs_dir", "logs"))
        ) / "Vein.log"
    else:
        resolved_game_log = server_dir / "Vein" / "Saved" / "Logs" / "Vein.log"

    save_games_cfg = cfg.get("save_games")
    uses_save_games_setting = isinstance(save_games_cfg, dict)
    save_games_override = (
        str(save_games_cfg.get("override") or "").strip()
        if uses_save_games_setting
        else str(_cfg_path_value(cfg, "save_dir", aliases=("saves_dir", "save_dir")) or "").strip()
    )
    resolved_save_games = (
        Path(save_games_override)
        if save_games_override
        else server_dir / "Vein" / "Saved" / "SaveGames"
    )

    return {
        "runtime_dir": rt,
        "server_dir": server_dir,
        "state_flag": rt / "server_running.flag",
        "shutdown_flag": rt / "shutdown_in_progress.flag",
        "server_state": rt / "server_state.json",
        "crash_state": rt / "crash_monitor_state.json",
        "logs_dir": resolved_game_log.parent,
        "absolute_log_file": resolved_game_log,
        "game_log_override": Path(game_log_override) if game_log_override else None,
        "save_dir": resolved_save_games,
        "save_games_override": Path(save_games_override) if save_games_override else None,
        "backup_root": backup_root,
        "features": cfg.get("features", {}),
        "log_monitor_enabled": bool(
            cfg.get("features", {}).get("enable_log_monitor", True)
        ),
        "crash_monitor_enabled": bool(
            cfg.get("features", {}).get("enable_crash_monitor", True)
        ),
        "hb_seconds": hb,
        "state_log": Path(monitor.get("state_file") or (rt / "log_monitor.state.json")),
    }


def _resolve_logfile(cfg_path: str, overrides: Dict[str, str]) -> Path:
    rp = _runtime_paths(cfg_path)
    candidates = [
        rp["absolute_log_file"],
        rp["logs_dir"] / "Vein.log",
        rp["server_dir"] / "Vein" / "Saved" / "Logs" / "Vein.log",
        rp["server_dir"] / "Saved" / "Logs" / "Vein.log",
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        key = str(candidate).casefold()
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    for candidate in unique:
        if candidate.is_file():
            return candidate
    return unique[0] if unique else rp["logs_dir"] / "Vein.log"


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
        return "-"
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
        return "-"



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
            # Make timezone-aware; ISO with 'Z' as '+00:00'
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
                # Fallback to shutdown/intent flag's PID if present
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
        ]
        self.edits: Dict[str, QtWidgets.QLineEdit] = {}
        row = 0
        for text, key in labels:
            grid.addWidget(QtWidgets.QLabel(text), row, 0)
            le = QtWidgets.QLineEdit()
            btn = QtWidgets.QToolButton()
            btn.setText("...")
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
            le.setText(str(ov.get(k, resolved.get(k, ""))))

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
        self._default_primary_sizes = [170, 1130]

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
        self._sync_guard = False
        self.nav_ctl = NavigationController(self)
        self.logs = LogPanelController(self)
        self.config_ctl = ConfigController(self)
        self.process_ctl = ProcessController(
            self,
            pyexe=_pyexe,
            resolved_paths=self._resolved_paths,
            rt_paths=_rt_paths,
            runtime_paths=_runtime_paths,
            spawn_logged=spawn_logged,
            run_once=run_once,
            mkflag=_mkflag,
            rm=_rm,
            wait_for_monitor_exit=_wait_for_monitor_exit,
            ctrl_dir=CTRL_DIR,
            packaged=bool(getattr(sys, "frozen", False)),
            tools_executable=ROOT / "VeinTools.exe",
        )
        self.status_renderer = StatusRenderer(self)

        # 1) build UI (creates tabs + self.chk_live, self.log_game/self.log_lm/self.log_cm)
        self._ui()

        # config renderer handles tab + filter state (wrapped by ConfigController)
        self.config_ctl.renderer = ConfigRenderer(self)
        self.config_renderer = self.config_ctl.renderer

        # 2) signals
        self._signals()  # should connect: b_clearlog-> _clear_current_log, chk_live-> _retail
        self.logs.connect_signals()

        # 3) config list + watch; first selection is applied after the combo is populated
        self.refresh_cfgs()
        self.watch_config()
        # Guarantee a real selection + load on first show
        QtCore.QTimer.singleShot(0, self._apply_default_selection)

        # 4) now it's safe to start tailing
        self.logs.initialize()

        # 5) background status polling
        self.status_bus = StatusBus(self)  # parented to the main window
        self.status_bus.ready.connect(self._status)
        self._pool = QtCore.QThreadPool.globalInstance()
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
        apply_design_system(container)
        self.setCentralWidget(container)
        root = QtWidgets.QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(build_command_bar(self, _dot))
        self._build_shortcuts_menu()

        views_bar = QtWidgets.QHBoxLayout()
        self.btn_toggle_left = QtWidgets.QToolButton()
        self.btn_toggle_left.setText("Show Navigation")
        self.btn_toggle_left.setCheckable(True)
        self.btn_toggle_left.setChecked(False)
        views_bar.addWidget(self.btn_toggle_left)
        views_bar.addStretch(1)
        root.addLayout(views_bar)

        monitor_items = [
            NavigationItem(
                "monitor.dashboard",
                "Home",
                "Server state, primary controls, monitors, and players",
            ),
            NavigationItem(
                "monitor.logs",
                "Logs",
                "Live server output, management logs, and errors",
            ),
        ]
        config_items = [
            NavigationItem(
                "monitor.quick_start",
                "Setup",
                "Install, select, or configure a Vein server",
            ),
            NavigationItem(
                "monitor.server_config",
                "Server Settings",
                "Review and safely edit supported Game.ini and Engine.ini values",
            ),
            NavigationItem(
                "monitor.config",
                "Advanced Config",
                "Management paths, features, backups, and monitor settings",
            ),
        ]

        self.nav_panel = NavigationPanel(monitor_items, config_items)

        self.primary_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.primary_splitter.setObjectName("primary_splitter")
        left_panel = build_left_panel(self, self.nav_panel)
        width_hint = self.nav_panel.property("fixed_width") or self.nav_panel.sizeHint().width()
        try:
            width_hint = int(width_hint)
        except Exception:
            width_hint = self.nav_panel.sizeHint().width()
        width_hint = max(140, width_hint)
        left_panel.setFixedWidth(width_hint)
        self.left_panel = left_panel
        self.primary_splitter.addWidget(left_panel)

        self.content_stack = QtWidgets.QStackedWidget()
        self.primary_splitter.addWidget(self.content_stack)
        self.primary_splitter.setStretchFactor(0, 0)
        self.primary_splitter.setStretchFactor(1, 1)
        self.primary_splitter.setCollapsible(0, True)
        root.addWidget(self.primary_splitter, 1)

        log_panel = build_log_panel(self)
        config_view = build_config_editor(self)
        JsonHL(self.json.document())
        self._default_primary_sizes = [
            max(self.left_panel.width(), 140),
            max(900, self.width() - self.left_panel.width()),
        ]
        self._apply_default_sizes()
        self.primary_splitter.splitterMoved.connect(self._sync_panel_buttons_from_splitters)
        self.logs.populate_log_sources()

        self._view_routes: dict[str, tuple[QtWidgets.QWidget, Optional[Callable[[], None]]]] = {}
        self._cached_admin_ids: set[str] | None = None
        dashboard = build_dashboard(self, _dot)
        self._register_view("monitor.dashboard", dashboard)
        self._register_view("monitor.logs", log_panel)
        self._register_view("monitor.config", config_view)
        server_config_view = build_server_config_preview_view(self)
        self._register_view(
            "monitor.server_config",
            server_config_view,
            self._refresh_server_config_preview,
        )
        quick_start_view = build_quick_start_view(self)
        self._register_view("monitor.quick_start", quick_start_view)

        self.nav_panel.viewSelected.connect(self._on_view_selected)
        self.nav_panel.set_default_selection("monitor.dashboard")
        self._on_view_selected("monitor.dashboard")

        self.btn_toggle_left.toggled.connect(self._set_left_panel_visible)
        self._set_left_panel_visible(True)
        self._sync_panel_buttons_from_splitters()

        bottom = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(6)

        self.state_box = QtWidgets.QTextBrowser()
        self.state_box.setMaximumHeight(60)
        self.state_box.setMinimumHeight(32)
        bottom_layout.addWidget(self.state_box, 1)

        self.lbl_watch = QtWidgets.QLabel("Watching for external config changes:")
        self.lbl_watch.setWordWrap(True)
        self.lbl_watch.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
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
        return self.nav_ctl.register_view(view_id, widget, on_show)

    def _on_view_selected(self, view_id: str):
        return self.nav_ctl.on_view_selected(view_id)

    def _ensure_tab_visible(self, tab_name: str):
        if tab_name == self._search_tab_name:
            self.config_ctl.ensure_search_tab()
        idx = self._tab_index(tab_name)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def _update_toggle_button(
        self,
        button: QtWidgets.QToolButton | None,
        visible: bool,
        show_text: str,
        hide_text: str,
    ):
        if not button:
            return
        button.blockSignals(True)
        button.setChecked(visible)
        button.setText(hide_text if visible else show_text)
        button.blockSignals(False)

    def _sync_panel_buttons_from_splitters(self):
        if self._sync_guard:
            return
        left_visible = True
        if hasattr(self, "primary_splitter"):
            sizes = self.primary_splitter.sizes()
            left_visible = bool(sizes and sizes[0] > 4)
        self._update_toggle_button(
            getattr(self, "btn_toggle_left", None),
            left_visible,
            "Show Navigation",
            "Hide Navigation",
        )

    def _build_shortcuts_menu(self):
        bar = self.menuBar()
        shortcuts = bar.addMenu("Shortcuts")
        shortcuts.addAction(
            "Open Logs Folder",
            lambda: self._open_folder(self._resolved_paths()["log_file"].parent),
        )
        shortcuts.addAction(
            "Open Runtime Status Folder",
            lambda: self._open_folder(_runtime_paths(self.config_path)["runtime_dir"]),
        )
        shortcuts.addAction(
            "Open Backups Folder",
            lambda: self._open_folder(_runtime_paths(self.config_path)["backup_root"]),
        )
        shortcuts.addAction(
            "Open Controller Folder", lambda: self._open_folder(CTRL_DIR)
        )
        shortcuts.addSeparator()
        shortcuts.addAction("Advanced...", self._open_advanced)

        help_menu = bar.addMenu("Help")
        help_menu.addAction("About Vein Server Manager", self._show_about)

    def _show_about(self):
        info = app_info.build_about_info(
            ROOT,
            config_path=self.config_path,
            frozen=bool(getattr(sys, "frozen", False)),
        )
        show_about_dialog(self, info)

    def _set_left_panel_visible(self, visible: bool):
        panel = getattr(self, "left_panel", None)
        splitter = getattr(self, "primary_splitter", None)
        if not panel or not splitter:
            return
        if self._sync_guard:
            return
        self._sync_guard = True
        panel.setVisible(visible)
        idx = splitter.indexOf(panel)
        if idx >= 0:
            sizes = splitter.sizes()
            width_hint = panel.width() or panel.sizeHint().width() or 140
            if visible:
                last = getattr(self, "_left_last_size", width_hint)
                if idx < len(sizes):
                    if sizes[idx] > 0:
                        last = sizes[idx]
                    else:
                        sizes[idx] = last
                else:
                    sizes.append(last)
                # keep the content area alive
                if len(sizes) == 2 and sizes[1 - idx] <= 0:
                    sizes[1 - idx] = max(600, last * 2)
                splitter.setSizes(sizes)
            else:
                if idx < len(splitter.sizes()):
                    self._left_last_size = max(width_hint, splitter.sizes()[idx])
                sizes = splitter.sizes()
                if idx < len(sizes):
                    sizes[idx] = 0
                    other = 1 - idx
                    if other < len(sizes) and sizes[other] <= 0:
                        sizes[other] = max(600, self.width() - 300)
                    splitter.setSizes(sizes)
        self._update_toggle_button(
            getattr(self, "btn_toggle_left", None),
            visible,
            "Show Navigation",
            "Hide Navigation",
        )
        self._sync_guard = False

    def _apply_default_sizes(self):
        if hasattr(self, "primary_splitter"):
            self.primary_splitter.setSizes(self._default_primary_sizes)
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
        timer.timeout.connect(lambda: self.config_ctl.apply_filter(self.filter.text()))

        self.b_clearfilter.clicked.connect(self.config_ctl.clear_filter)

        self.btnBkNow.clicked.connect(self._on_backup_now_clicked)
        self.btnBkOpen.clicked.connect(self._on_open_backups_clicked)
        self.btnPreflightRefresh.clicked.connect(self._kick_preflight_check)
        if hasattr(self, "btnServerConfigPreviewRefresh"):
            self.btnServerConfigPreviewRefresh.clicked.connect(self._refresh_server_config_preview)
        if hasattr(self, "treeServerConfigPreview"):
            self.treeServerConfigPreview.itemSelectionChanged.connect(self._server_config_selection_changed)
        if hasattr(self, "btnServerConfigEditPreview"):
            self.btnServerConfigEditPreview.clicked.connect(self._preview_server_config_edit)
        if hasattr(self, "btnServerConfigEditApply"):
            self.btnServerConfigEditApply.clicked.connect(self._confirm_apply_server_config_edit)
        if hasattr(self, "txtServerConfigEditValue"):
            self.txtServerConfigEditValue.textChanged.connect(
                lambda: self.btnServerConfigEditApply.setEnabled(False)
                if hasattr(self, "btnServerConfigEditApply")
                else None
            )
        if hasattr(self, "btnQuickStartPreview"):
            self.btnQuickStartPreview.clicked.connect(self._build_quick_start_preview)
        if hasattr(self, "btnQuickStartApply"):
            self.btnQuickStartApply.clicked.connect(self._confirm_apply_quick_start)
        if hasattr(self, "cmbQuickSetupMode"):
            self.cmbQuickSetupMode.currentIndexChanged.connect(
                self._quick_start_mode_changed
            )
        if hasattr(self, "btnQuickStartBrowseRoot"):
            self.btnQuickStartBrowseRoot.clicked.connect(self._browse_quick_start_server_root)
        if hasattr(self, "btnQuickStartBrowseSteamCmd"):
            self.btnQuickStartBrowseSteamCmd.clicked.connect(self._browse_quick_start_steamcmd)
        if hasattr(self, "btnQuickGameLogBrowse"):
            self.btnQuickGameLogBrowse.clicked.connect(self._browse_quick_start_game_log)
        if hasattr(self, "btnQuickSaveGamesBrowse"):
            self.btnQuickSaveGamesBrowse.clicked.connect(self._browse_quick_start_save_games)
        if hasattr(self, "btnQuickStartLoadExisting"):
            self.btnQuickStartLoadExisting.clicked.connect(self._load_existing_quick_start_settings)
        if hasattr(self, "edQuickServerRoot"):
            self.edQuickServerRoot.editingFinished.connect(self._inspect_quick_start_server_root)
            QtCore.QTimer.singleShot(0, self._initialize_quick_start_mode)

        self.b_server_action.clicked.connect(self._activate_primary_server_action)
        self.b_restart.clicked.connect(self.restart_server)
        self.a_lm_on.triggered.connect(self.start_lm)
        self.a_lm_off.triggered.connect(self.stop_lm)
        self.a_cm_on.triggered.connect(self.start_cm)
        self.a_cm_off.triggered.connect(self.stop_cm)

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
        self.config_ctl.cfg_selected(name)

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
            self.config_ctl.build_tabs(self._data)

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
        elif self._cfg_kind == "yaml":
            new_text = _dump_any_config(self._data, "yaml")
        else:
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
            self._status("Config parses OK")
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
            QtCore.QTimer.singleShot(250, self._kick_preflight_check)
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
        # Prefer the monitor's notion of the active file if available
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
        return self.logs.retail()

    def _tail_stop_all(self):
        return self.logs.tail_stop_all()

    def _retail(self):
        return self.logs.retail()

    def _populate_log_sources(self):
        return self.logs.populate_log_sources()

    def _run_log_search(self):
        return self.logs._run_log_search()

    def _log_search_ready(self, payload: list[dict]):
        return self.logs._log_search_ready(payload)

    def _log_search_error(self, message: str):
        return self.logs._log_search_error(message)

    def _clear_log_search(self):
        return self.logs._clear_log_search()

    def _refresh_mgmt_log_files(self):
        return self.logs._refresh_mgmt_log_files()

    def _collect_subsystem_files(self, subsystem: str) -> list[tuple[Path, str]]:
        return self.logs._collect_subsystem_files(subsystem)

    def _collect_archive_files(self) -> list[tuple[Path, str]]:
        return self.logs._collect_archive_files()

    def _infer_subsystem_from_path(self, path: Path) -> str:
        return self.logs._infer_subsystem_from_path(path)

    def _archive_logs_now(self):
        return self.logs._archive_logs_now()

    def _archive_logs_done(self, moved: list[tuple[Path, Path]]):
        return self.logs._archive_logs_done(moved)

    def _archive_logs_error(self, message: str):
        return self.logs._archive_logs_error(message)

    def _current_mgmt_log_file(self) -> Path | None:
        return self.logs._current_mgmt_log_file()

    def _load_mgmt_log_file(
        self,
        auto: bool = False,
        *,
        highlight_line: Optional[int] = None,
        highlight_level: Optional[str] = None,
    ):
        return self.logs._load_mgmt_log_file(
            auto=auto,
            highlight_line=highlight_line,
            highlight_level=highlight_level,
        )

    def _open_selected_mgmt_folder(self):
        return self.logs._open_selected_mgmt_folder()

    def _format_timestamp(self, ts: float) -> str:
        return self.logs._format_timestamp(ts)

    def _refresh_error_events(self):
        return self.logs._refresh_error_events()

    def _error_ready(self, payload: list[dict]):
        return self.logs._error_ready(payload)

    def _error_error(self, message: str):
        return self.logs._error_error(message)

    def _open_error_log_from_table(self, item):
        return self.logs._open_error_log_from_table(item)

    def _ensure_subsystem_selected(self, subsystem: str, archived: bool = False) -> None:
        return self.logs._ensure_subsystem_selected(subsystem, archived=archived)

    def _load_log_into_subsystem_tab(
        self,
        rel_path: str,
        line: int,
        *,
        subsystem: str,
        level: Optional[str],
    ):
        return self.logs._load_log_into_subsystem_tab(
            rel_path,
            line,
            subsystem=subsystem,
            level=level,
        )

    def _highlight_log_line(
        self, line_no: int, level: Optional[str] = None
    ) -> None:
        return self.logs._highlight_log_line(line_no, level)

    def _highlight_color_for_level(self, level: Optional[str]) -> str:
        return self.logs._highlight_color_for_level(level)

    @QtCore.Slot(str)
    def _on_game_line(self, s: str):
        return self.logs._on_game_line(s)

    @QtCore.Slot(str)
    def _on_lm_line(self, s: str):
        return self.logs._on_lm_line(s)

    @QtCore.Slot(str)
    def _on_cm_line(self, s: str):
        return self.logs._on_cm_line(s)

    def _flush_tail(self):
        return self.logs._flush_tail()

    # ------------------------ Server / monitors -------------------------------
    def _resolved_paths(self) -> Dict[str, Path]:
        ov = {} if self.use_defaults else self.overrides
        return _resolved_paths(self.config_path, ov)

    def start_server(self):
        return self.process_ctl.start_server()

    def _activate_primary_server_action(self):
        action = self.b_server_action.property("serverAction")
        if action == "setup":
            self._on_view_selected("monitor.quick_start")
        elif action == "start":
            self.start_server()
        elif action == "stop":
            self.stop_server()

    def stop_server(self):
        return self.process_ctl.stop_server()

    def restart_server(self):
        return self.process_ctl.restart_server()

    def start_lm(self):
        return self.process_ctl.start_lm()

    def stop_lm(self):
        return self.process_ctl.stop_lm()

    def start_cm(self):
        return self.process_ctl.start_cm()

    def stop_cm(self):
        return self.process_ctl.stop_cm()

    # ----------------------- Background status wiring -------------------------
    def _apply_status_snapshot(self, snap: dict):
        return self.status_renderer.apply(snap)

    def _apply_status_snapshot_impl(self, snap: dict):
        # Update gumballs without blocking
        def dot(on, warn=False):
            return _dot(on, warn)

        # Server
        server_on = bool(snap.get("server", False))
        server_available = bool(snap.get("server_available", False))
        action_state = server_action_state(server_available, server_on)
        lm_on = bool(snap.get("logmon", False))
        lm_fresh = bool(snap.get("logmon_fresh", False))
        cm_on = bool(snap.get("crashmon", False))
        self._server_available = server_available
        self.dot_srv.setStyleSheet(dot(server_on))
        self.lbl_server_state.setText(action_state["label"])
        server_action_busy = bool(getattr(self, "_server_action_busy", False))
        if not server_action_busy:
            self.b_server_action.setText(action_state["primary_label"])
            self.b_server_action.setProperty(
                "serverAction", action_state["primary_action"]
            )
            role = action_state["primary_role"]
            if self.b_server_action.property("buttonRole") != role:
                set_button_role(self.b_server_action, role)
            self.b_server_action.setEnabled(True)
            self.b_restart.setEnabled(action_state["can_restart"])
        else:
            self.b_server_action.setText(
                getattr(self, "_server_action_busy_label", "") or "Working..."
            )
            self.b_server_action.setEnabled(False)
            self.b_restart.setEnabled(False)
        self.a_lm_on.setEnabled(server_available and not lm_on)
        self.a_lm_off.setEnabled(lm_on)
        self.a_cm_on.setEnabled(server_available and not cm_on)
        self.a_cm_off.setEnabled(cm_on)
        self.b_monitors.setEnabled(
            any(
                action.isEnabled()
                for action in (
                    self.a_lm_on,
                    self.a_lm_off,
                    self.a_cm_on,
                    self.a_cm_off,
                )
            )
        )
        if server_on:
            self.b_server_action.setToolTip("Safely stop the running Vein server")
            self.b_restart.setToolTip("Safely stop and restart the Vein server")
        elif not server_available:
            guidance = "No Vein server is installed or selected. Open Quick Start to install or configure one."
            self.b_server_action.setToolTip(
                "Open Setup to install or select a Vein server"
            )
            self.b_restart.setToolTip(guidance)
            self.a_lm_on.setToolTip(guidance)
            self.a_cm_on.setToolTip(guidance)
            self.status_label.setText(f"Status: {guidance}")
        else:
            self.b_server_action.setToolTip("Start the configured Vein server")
        # Log monitor: green if alive+fresh; yellow if alive but stale
        self.dot_lm.setStyleSheet(
            dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh))
        )
        # Crash monitor
        self.dot_cm.setStyleSheet(dot(cm_on))
        log_state = (
            "running" if lm_on and lm_fresh else "stale" if lm_on else "stopped"
        )
        crash_state = "running" if cm_on else "stopped"
        self.lbl_monitor_state.setText(
            f"Log {log_state} · Crash {crash_state}"
        )
        cmode = snap.get("crash_mode", "unknown")
        self.lblCrashMode.setText(cmode)
        self.a_cm_on.setToolTip(f"Crash monitor mode: {cmode}")
        self.a_cm_off.setToolTip(f"Crash monitor mode: {cmode}")

        # Dashboard detail (read server_state only once here)
        rp = _runtime_paths(self.config_path)
        rt = _rt_paths(self.config_path)
        st = self._safe_json(rp["server_state"])
        lms = self._safe_json(rt["state_log"])
        last = lms.get("last_updated") if lms else None
        self.lblLogDot.setStyleSheet(
            dot(lm_on and lm_fresh, warn=(lm_on and not lm_fresh))
        )
        monitor_status = str(lms.get("status") or "").strip() if lms else ""
        monitor_message = str(lms.get("message") or "").strip() if lms else ""
        status_labels = {
            "waiting_for_log": "waiting for game log",
            "server_offline": "idle (server offline)",
            "tailing": "tailing game log",
            "read_error": "game log read error",
            "stopped": "stopped",
        }
        self.lblLogStatus.setText(
            status_labels.get(monitor_status, "running" if lm_on else "stopped")
        )
        self.lblLogStatus.setToolTip(monitor_message)
        last_line = lms.get("last_line_at") if lms else None
        if last_line:
            self.lblLogLast.setText(f"Last game log activity: {_age_str(last_line)}")
        else:
            self.lblLogLast.setText(f"Last monitor update: {_age_str(last)}")
        server_joinable = runtime_server_joinable(st, lms)
        runtime_state = dict(st or {})
        runtime_state["server_joinable"] = server_joinable
        runtime_labels = server_runtime_labels(server_on, runtime_state)
        self.lblLogJoin.setText(runtime_labels["joinable"])
        self.lblLogPlayers.setText(runtime_labels["players"])
        self.lblLogUptime.setText(runtime_labels["uptime"])

        if getattr(self, "_startup_feedback_tracking", False):
            feedback = startup_runtime_feedback(
                server_running=server_on,
                server_joinable=server_joinable,
                log_monitor_running=lm_on,
                crash_monitor_running=cm_on,
            )
            if feedback:
                set_startup_feedback(
                    self,
                    feedback["text"],
                    step=feedback["step"],
                    state=feedback["state"],
                )
                if feedback["state"] == "complete":
                    self._startup_feedback_tracking = False

        http_state = lms.get("http_api") if isinstance(lms, dict) else None

        self._update_http_api_summary(http_state, server_online=server_on)
        player_snapshot = {}
        snap_path = rt.get("player_snapshot")
        if snap_path:
            player_snapshot = self._safe_json(snap_path)
        self._render_player_tree(player_snapshot, server_online=server_on)

        # Hint the tailer in case path switched (next poll will re-open)
        tail_game = getattr(getattr(self, "logs", None), "tail_game", None)
        if tail_game:
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
        bk_last = bk.get("last_utc") or "-"
        bk_file = bk.get("last_zip") or "-"
        bk_total = (bk.get("counts") or {}).get("TOTAL", 0)

        # --- Backups card update ---
        bk_enabled = bool((snap.get("backup") or {}).get("enabled", True))
        bk_counts = (snap.get("backup") or {}).get("counts") or {}
        age = _age_str(bk_last) if bk_last and bk_last != "-" else "-"

        home_health = home_health_state(
            server_available=server_available,
            server_running=server_on,
            log_monitor_running=lm_on,
            log_monitor_fresh=lm_fresh,
            crash_monitor_running=cm_on,
            backups_enabled=bk_enabled,
        )
        for badge, key in (
            (self.badgeHomeServer, "server"),
            (self.badgeHomeLogMonitor, "log_monitor"),
            (self.badgeHomeCrashMonitor, "crash_monitor"),
            (self.badgeHomeBackups, "backups"),
        ):
            badge_state = home_health[key]
            if (
                badge.property("statusState") != badge_state["state"]
                or badge.text() != badge_state["text"]
            ):
                badge.set_state(badge_state["state"], badge_state["text"])
        guidance = home_health["guidance"]
        if self.noticeHomeGuidance.text() != guidance["text"]:
            self.noticeHomeGuidance.setText(guidance["text"])
        if self.noticeHomeGuidance.property("noticeKind") != guidance["kind"]:
            self.noticeHomeGuidance.set_kind(guidance["kind"])

        def _fmt_counts(d: dict) -> str:
            if not d:
                return "-"
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
            f"Backup: Last={bk_last} - File={bk_file} - Total={bk_total}"
        )

        # Nice UX touch: show details on the "Open Backups" button
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
            lm_on = bool(snap.get("logmon", False))
            lm_fresh = bool(snap.get("logmon_fresh", False))
            now = time.time()

            cfg = _load_cfg_for_runtime(self.config_path)
            features = cfg.get("features", {})
            logmon_enabled = features.get("enable_log_monitor", True)

            # also check if a manual stop flag exists to respect user intent
            rt = _rt_paths(self.config_path)
            manual_stop = rt["stop_log"].exists() if "stop_log" in rt else False

            if should_autostart_log_monitor(
                server_running=server_on,
                monitor_enabled=logmon_enabled,
                monitor_running=lm_on,
                manual_stop=manual_stop,
                lifecycle_busy=bool(getattr(self, "_server_action_busy", False)),
                shutdown_in_progress=_file_exists(rp["shutdown_flag"]),
            ) and (now - self._lm_autostart_last) > 5.0:
                self._lm_autostart_last = now
                self.start_lm()
        except Exception:
            pass

    def _update_http_api_summary(
        self, http_state: Optional[dict], *, server_online: bool = True
    ) -> None:
        if not hasattr(self, "lblLogHttpStatus"):
            return

        status_text = "HTTP API: disabled"
        players_text = "API Players: -"
        world_text = "World Time: -"
        weather_text = "Weather: -"

        if not server_online:
            self.lblLogHttpStatus.setText("HTTP API: unavailable (server offline)")
            self.lblLogHttpPlayers.setText("API Players: 0 (server offline)")
            self.lblLogHttpWorld.setText("World Time: unavailable (server offline)")
            self.lblLogHttpWeather.setText("Weather: unavailable (server offline)")
            return

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

    def _render_player_tree(
        self, snapshot: Optional[dict], *, server_online: bool = True
    ) -> None:
        if not hasattr(self, "playerTree"):
            return
        data = normalize_player_snapshot(snapshot, server_online)
        self._player_snapshot_raw = data
        cache_entries = self._update_player_cache(data)

        admins = data.get("admins") or []
        if not server_online:
            self.lblAdminList.setText("Admins online: none (server offline)")
        elif admins:
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
            prefix = "Players refreshed" if server_online else "Last known player data"
            self.lblPlayerSnapshotTs.setText(f"{prefix}: {age} ago")
        else:
            self.lblPlayerSnapshotTs.setText("Players refreshed: -")

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
                detail_bits.append("API verified")
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
                    detail += f" - playing {current_char_name}"
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
        label = "World Time: -"
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
            return "Weather: -"

        parts: list[str] = []
        temp = payload.get("temperature")
        if isinstance(temp, (int, float)):
            parts.append(f"{temp:.1f} degC")

        humidity = payload.get("relativeHumidity")
        if isinstance(humidity, (int, float)):
            pct = humidity * 100 if humidity <= 1 else humidity
            parts.append(f"humidity {pct:.0f}%")

        wind_dir = payload.get("windDirection")
        wind_force = payload.get("windForce")
        if isinstance(wind_dir, (int, float)) and isinstance(wind_force, (int, float)):
            parts.append(f"wind {wind_dir:.0f} deg @ {wind_force:.1f}")

        precip = payload.get("precipitation")
        if isinstance(precip, (int, float)):
            parts.append(f"precip {precip:.2f}")

        if not parts:
            return "Weather: -"
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
        if self._poller is not None:
            return
        worker = StatusPoller(self.config_path, _load_any_config)
        worker.signals.ready.connect(self._apply_status_snapshot)
        worker.signals.finished.connect(self._status_poll_finished)
        self._poller = worker
        self._pool.start(worker)

    @QtCore.Slot()
    def _status_poll_finished(self):
        self._poller = None

    def _kick_preflight_check(self):
        if getattr(self, "_preflight_running", False):
            return
        if not getattr(self, "config_path", ""):
            return
        self._preflight_running = True
        if hasattr(self, "lblPreflightSummary"):
            self.lblPreflightSummary.setText("Checking server install and config.")
        worker = PreflightWorker(self.config_path)
        worker.signals.ready.connect(self._apply_preflight_snapshot)
        self._pool.start(worker)

    def _apply_preflight_snapshot(self, payload: dict):
        self._preflight_running = False
        counts = payload.get("summary") or {}
        headline = payload.get("headline") or "Preflight complete"
        if hasattr(self, "lblPreflightSummary"):
            self.lblPreflightSummary.setText(
                f"{headline} | PASS={counts.get('PASS', 0)} INFO={counts.get('INFO', 0)} WARN={counts.get('WARN', 0)} FAIL={counts.get('FAIL', 0)}"
            )
        problems = payload.get("problems") or []
        lines = []
        for item in problems[:5]:
            lines.append(
                f"[{item.get('status', '?')}] {item.get('name', 'check')}: {item.get('message', '')}"
            )
        if hasattr(self, "lblPreflightDetails"):
            self.lblPreflightDetails.setText("\n".join(lines) if lines else "No preflight issues found.")

    def _refresh_server_config_preview(self):
        if getattr(self, "_server_config_preview_running", False):
            return
        if not getattr(self, "config_path", ""):
            return
        self._server_config_preview_running = True
        if hasattr(self, "lblServerConfigPreviewStatus"):
            self.lblServerConfigPreviewStatus.setText("Loading Game.ini and Engine.ini.")
        worker = ServerConfigPreviewWorker(self.config_path)
        worker.signals.ready.connect(self._apply_server_config_preview)
        self._pool.start(worker)

    def _apply_server_config_preview(self, payload: dict):
        self._server_config_preview_running = False
        tree = getattr(self, "treeServerConfigPreview", None)
        if tree is None:
            return
        tree.clear()
        error = payload.get("error") or ""
        missing = payload.get("missing_files") or []
        items = payload.get("items") or []
        if error:
            status = f"Preview failed: {error}"
        elif missing:
            status = f"Loaded {len(items)} setting(s); missing file(s): {len(missing)}"
        else:
            status = f"Loaded {len(items)} setting(s)."
        if hasattr(self, "lblServerConfigPreviewStatus"):
            self.lblServerConfigPreviewStatus.setText(status)

        for item in items:
            state = "set" if item.get("present") else "not set"
            row = QtWidgets.QTreeWidgetItem(
                [
                    str(item.get("source") or ""),
                    str(item.get("section") or ""),
                    str(item.get("key") or ""),
                    str(item.get("value") or ""),
                    state,
                ]
            )
            tree.addTopLevelItem(row)
        for idx in range(tree.columnCount()):
            tree.resizeColumnToContents(idx)
        self._server_config_selection_changed()

    def _selected_server_config_item(self):
        tree = getattr(self, "treeServerConfigPreview", None)
        if tree is None:
            return None
        items = tree.selectedItems()
        return items[0] if items else None

    def _server_config_selection_changed(self):
        item = self._selected_server_config_item()
        if item is None:
            if hasattr(self, "lblServerConfigEditTarget"):
                self.lblServerConfigEditTarget.setText("Select a setting to edit.")
            return
        source, section, key, value = [item.text(i) for i in range(4)]
        if hasattr(self, "lblServerConfigEditTarget"):
            self.lblServerConfigEditTarget.setText(f"{source} [{section}] {key}")
        if hasattr(self, "txtServerConfigEditValue"):
            if value.startswith("<") and value.endswith(">"):
                self.txtServerConfigEditValue.setPlainText("")
                self.txtServerConfigEditValue.setPlaceholderText("Sensitive value is masked. Enter the replacement value.")
            else:
                self.txtServerConfigEditValue.setPlainText("" if value == "(not set)" else value)
        if hasattr(self, "txtServerConfigEditDiff"):
            self.txtServerConfigEditDiff.clear()
        if hasattr(self, "btnServerConfigEditApply"):
            self.btnServerConfigEditApply.setEnabled(False)

    def _start_server_config_edit_worker(self, action: str):
        item = self._selected_server_config_item()
        if item is None or getattr(self, "_server_config_edit_running", False):
            return
        self._server_config_edit_running = True
        self.btnServerConfigEditApply.setEnabled(False)
        source, section, key = [item.text(i) for i in range(3)]
        value_text = self.txtServerConfigEditValue.toPlainText()
        worker = ServerConfigEditWorker(
            self.config_path,
            action=action,
            source=source,
            section=section,
            key=key,
            value_text=value_text,
        )
        worker.signals.ready.connect(self._apply_server_config_edit_result)
        self._pool.start(worker)

    def _preview_server_config_edit(self):
        if hasattr(self, "txtServerConfigEditDiff"):
            self.txtServerConfigEditDiff.setPlainText("Building diff preview.")
        self._start_server_config_edit_worker("preview")

    def _confirm_apply_server_config_edit(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            "Apply Server Config Change",
            "This will back up and modify the selected Vein server config file. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer == QtWidgets.QMessageBox.Yes:
            self._start_server_config_edit_worker("apply")

    def _apply_server_config_edit_result(self, payload: dict):
        self._server_config_edit_running = False
        ok = bool(payload.get("ok"))
        action = payload.get("action") or "preview"
        if not ok:
            message = f"Edit {action} failed: {payload.get('error') or 'unknown error'}"
            if hasattr(self, "txtServerConfigEditDiff"):
                self.txtServerConfigEditDiff.setPlainText(message)
            self._status(message)
            return

        diffs = payload.get("diffs") or {}
        diff_text = "\n".join(str(value) for value in diffs.values()).strip()
        if not diff_text:
            diff_text = "No file changes required."
        if hasattr(self, "txtServerConfigEditDiff"):
            self.txtServerConfigEditDiff.setPlainText(diff_text)
        if hasattr(self, "btnServerConfigEditApply"):
            self.btnServerConfigEditApply.setEnabled(action == "preview" and bool(payload.get("changed_files")))
        if action == "apply":
            backups = payload.get("backups") or []
            self._status(f"Server config saved. Backup file(s): {len(backups)}")
            self._refresh_server_config_preview()
            self._kick_preflight_check()
        else:
            self._status("Server config diff preview ready.")

    def _build_quick_start_preview(self):
        if self.cmbQuickSetupMode.currentData() == "new":
            self._inspect_quick_start_server_root()
            if self.cmbQuickSetupMode.currentData() == "existing":
                self._status("Existing server detected; loading its current settings before preview.")
                return
        try:
            preview = build_quick_start_preview(self)
        except Exception as exc:
            preview = f"Quick Start preview failed:\n{exc}"
            self._status(f"Quick Start preview failed: {exc}")
            self.lblQuickStartStatus.setText(f"Preview failed: {exc}")
            self.lblQuickStartStatus.set_kind("error")
            if hasattr(self, "btnQuickStartApply"):
                self.btnQuickStartApply.setEnabled(False)
        else:
            self._status("Quick Start preview ready.")
            self.lblQuickStartStatus.setText(
                "Preview ready. Review every proposed change before applying setup."
            )
            self.lblQuickStartStatus.set_kind("info")
            if hasattr(self, "btnQuickStartApply"):
                self.btnQuickStartApply.setEnabled("Can apply: yes" in preview)
        if hasattr(self, "txtQuickStartPreview"):
            self.txtQuickStartPreview.setPlainText(preview)

    def _browse_quick_start_server_root(self):
        current = self.edQuickServerRoot.text().strip() or str(ROOT)
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Vein Server Folder", current)
        if selected:
            self.edQuickServerRoot.setText(selected)
            self._inspect_quick_start_server_root()

    def _browse_quick_start_steamcmd(self):
        current = Path(self.edQuickSteamCmd.text().strip() or "SteamCMD/steamcmd.exe").expanduser()
        start = current if current.is_dir() else current.parent
        selected, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select SteamCMD Executable",
            str(start),
            "SteamCMD (steamcmd.exe);;Executable files (*.exe);;All files (*)",
        )
        if selected:
            self.edQuickSteamCmd.setText(selected)

    def _browse_quick_start_game_log(self):
        current = Path(
            self.edQuickGameLogOverride.text().strip()
            or self.edQuickGameLogResolved.text().strip()
            or "Vein.log"
        ).expanduser()
        selected, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Vein Game Log",
            str(current.parent),
            "Vein game log (Vein.log);;Log files (*.log);;All files (*)",
        )
        if selected:
            self.grpQuickGameLogOverride.setChecked(True)
            self.edQuickGameLogOverride.setText(selected)

    def _browse_quick_start_save_games(self):
        current = Path(
            self.edQuickSaveGamesOverride.text().strip()
            or self.edQuickSaveGamesResolved.text().strip()
            or "SaveGames"
        ).expanduser()
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Vein SaveGames Folder",
            str(current),
        )
        if selected:
            self.grpQuickSaveGamesOverride.setChecked(True)
            self.edQuickSaveGamesOverride.setText(selected)

    def _quick_start_runtime_paths(self):
        cfg = _load_cfg_for_runtime(self.config_path)
        configured_root = str(cfg.get("server_dir") or "").strip()
        executables = [
            str(item) for item in (cfg.get("server_executables") or []) if str(item).strip()
        ]
        steamcmd_path = str(cfg.get("steamcmd_path") or "").strip()
        game_log_override = str(cfg.get("game_log_override") or "").strip()
        save_games_override = str(cfg.get("save_games_override") or "").strip()
        self._quick_start_existing_executables = executables
        return (
            configured_root,
            steamcmd_path,
            executables,
            game_log_override,
            save_games_override,
        )

    def _initialize_quick_start_mode(self):
        configured_root, steamcmd_path, executables, game_log_override, save_games_override = self._quick_start_runtime_paths()
        if steamcmd_path:
            self.edQuickSteamCmd.setText(steamcmd_path)
        self.edQuickGameLogOverride.setText(game_log_override)
        self.grpQuickGameLogOverride.setChecked(bool(game_log_override))
        self.edQuickSaveGamesOverride.setText(save_games_override)
        self.grpQuickSaveGamesOverride.setChecked(bool(save_games_override))
        update_quick_start_save_games_path(self)
        update_quick_start_game_log_path(self)
        if configured_root:
            inspection = inspect_server_root(configured_root, executables or None)
            if inspection.is_existing_server:
                self.edQuickServerRoot.setText(configured_root)
                enforce_quick_start_root_mode(self, inspection)

    def _inspect_quick_start_server_root(self):
        root = self.edQuickServerRoot.text().strip()
        if not root:
            return
        _, _, executables, _, _ = self._quick_start_runtime_paths()
        inspection = inspect_server_root(root, executables or None)
        if enforce_quick_start_root_mode(self, inspection):
            if self.cmbQuickSetupMode.currentData() == "existing" and not getattr(
                self, "_quick_start_load_running", False
            ):
                self._load_existing_quick_start_settings()
            return
        if inspection.state == "occupied" and self.cmbQuickSetupMode.currentData() == "new":
            self.lblQuickStartStatus.setText(
                "New Server requires a missing or empty destination folder. Choose another folder."
            )
            self.lblQuickStartStatus.set_kind("warning")

    def _quick_start_mode_changed(self, *_):
        mode = self.cmbQuickSetupMode.currentData()
        set_quick_start_mode(self, mode)
        if mode != "existing":
            self._inspect_quick_start_server_root()
            return

        configured_root, steamcmd_path, _, _, _ = self._quick_start_runtime_paths()
        detected_root = str(getattr(self, "_quick_start_auto_detected_root", "") or "").strip()
        self._quick_start_auto_detected_root = ""
        current_root = self.edQuickServerRoot.text().strip()
        current_inspection = inspect_server_root(
            current_root, getattr(self, "_quick_start_existing_executables", None) or None
        ) if current_root else None
        selected_root = detected_root
        if not selected_root and current_inspection is not None and current_inspection.is_existing_server:
            selected_root = current_root
        selected_root = selected_root or configured_root
        if selected_root:
            self.edQuickServerRoot.setText(selected_root)
        if steamcmd_path:
            self.edQuickSteamCmd.setText(steamcmd_path)
        if selected_root:
            self._load_existing_quick_start_settings()

    def _load_existing_quick_start_settings(self):
        if getattr(self, "_quick_start_load_running", False):
            return
        self._quick_start_load_running = True
        self.btnQuickStartLoadExisting.setEnabled(False)
        self.lblQuickStartStatus.setText("Loading existing Game.ini and Engine.ini settings.")
        self.lblQuickStartStatus.set_kind("info")
        worker = ExistingServerLoadWorker(
            self.edQuickServerRoot.text().strip(),
            getattr(self, "_quick_start_existing_executables", None),
        )
        worker.signals.ready.connect(self._apply_existing_quick_start_settings)
        self._pool.start(worker)

    def _apply_existing_quick_start_settings(self, payload: dict):
        self._quick_start_load_running = False
        self.btnQuickStartLoadExisting.setEnabled(True)
        if not payload.get("ok"):
            message = f"Existing server load failed: {payload.get('error') or 'unknown error'}"
            self.lblQuickStartStatus.setText(message)
            self.lblQuickStartStatus.set_kind("error")
            self._status(message)
            return

        settings = ExistingServerSettings(
            server_root=payload["server_root"],
            values=dict(payload.get("values") or {}),
            loaded_fields=tuple(payload.get("loaded_fields") or ()),
            missing_files=tuple(payload.get("missing_files") or ()),
            password_configured=payload.get("password_configured"),
            discord_chat_webhook_configured=payload.get("discord_chat_webhook_configured"),
            discord_admin_webhook_configured=payload.get("discord_admin_webhook_configured"),
        )
        populate_existing_server_settings(self, settings)
        missing = len(settings.missing_files)
        status = f"Loaded {len(settings.loaded_fields)} existing setting(s)"
        if missing:
            status += f"; {missing} config file(s) not found"
        self.lblQuickStartStatus.setText(status + ". Edit only the values you want to change, then build a preview.")
        self.lblQuickStartStatus.set_kind("success")
        self._status(status + ".")

    def _confirm_apply_quick_start(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            "Apply Quick Start Setup",
            "This will update the local management config and, if the selected server root exists, back up and modify Game.ini/Engine.ini. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            result = apply_quick_start(self)
        except Exception as exc:
            result = f"Quick Start apply failed:\n{exc}"
            self._status(f"Quick Start apply failed: {exc}")
            self.lblQuickStartStatus.setText(f"Setup failed: {exc}")
            self.lblQuickStartStatus.set_kind("error")
        else:
            self._status("Quick Start setup applied.")
            self.lblQuickStartStatus.setText(
                "Setup applied successfully. Preflight and server configuration are refreshing."
            )
            self.lblQuickStartStatus.set_kind("success")
            QtCore.QTimer.singleShot(300, self.load_config_text)
            self._refresh_server_config_preview()
            self._kick_preflight_check()
        if hasattr(self, "txtQuickStartPreview"):
            self.txtQuickStartPreview.setPlainText(result)

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

    def _notify_action_error(
        self, title: str, message: str, log_path: Path | None = None
    ) -> None:
        details = message
        if log_path:
            details += f"\n\nStartup output file\n{log_path}"
        details += f"\n\nActive configuration\n{self.config_path}"
        QtWidgets.QMessageBox.critical(self, title, details)

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
    try:
        rc = app.exec()
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
