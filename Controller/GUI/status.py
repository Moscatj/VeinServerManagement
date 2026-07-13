"""
Status poller and bus helpers for Vein Manager.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from PySide6 import QtCore

from Tools.config_io import load_and_validate_config

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class StatusBus(QtCore.QObject):
    ready = QtCore.Signal(dict)


class StatusSnapshot(QtCore.QObject):
    ready = QtCore.Signal(dict)
    finished = QtCore.Signal()


class StatusPoller(QtCore.QRunnable):
    """
    Reads Runtime pid/flags and small JSONs off the UI thread and returns a compact snapshot:
      {'server':bool,'logmon':bool,'logmon_fresh':bool,'crashmon':bool,'crash_mode':str}
    """

    def __init__(self, cfg_path: str, load_any_config: Callable[[str | Path], tuple]):
        super().__init__()
        self.cfg_path = cfg_path
        self._load_any_config = load_any_config
        self.signals = StatusSnapshot()
        self._last_tasklist_at = 0.0
        self.stop_flag = False

        vcfg = None
        try:
            vcfg = load_and_validate_config(cfg_path, fatal=False)
        except Exception:
            vcfg = None

        if vcfg:
            self.hb_seconds = getattr(vcfg, "hb_seconds", 60)
            self.fresh_mult = getattr(vcfg, "fresh_window_multiplier", 2.0)
            self.paths = {
                "server_dir": getattr(vcfg, "server_dir", ""),
                "runtime_dir": getattr(vcfg, "runtime_dir", ""),
                "logs_dir": getattr(vcfg, "logs_dir", ""),
                "save_dir": getattr(vcfg, "save_dir", ""),
            }
            self.selected_exe = getattr(vcfg, "selected_exe", "")
            backups = getattr(vcfg, "backups", {}) or {}
            self.backups_enabled = bool(backups.get("enable", True))
        else:
            obj, kind, _ = self._load_any_config(cfg_path)
            obj = obj if isinstance(obj, dict) else {}

            p = obj.get("paths", {}) or {}
            self.paths = {
                "server_dir": p.get("server") or p.get("server_dir") or "",
                "runtime_dir": p.get("runtime") or p.get("runtime_dir") or "",
                "logs_dir": p.get("logs") or p.get("logs_dir") or "",
                "save_dir": p.get("saves") or p.get("save_dir") or "",
            }

            lm = obj.get("log_monitor", {}) or {}
            mon = obj.get("monitor", {}) or {}
            self.hb_seconds = int(
                lm.get(
                    "heartbeat_seconds",
                    lm.get(
                        "heartbeat_interval_seconds",
                        mon.get(
                            "heartbeat_seconds",
                            mon.get("heartbeat_interval_seconds", 60),
                        ),
                    ),
                )
            )
            self.hb_seconds = max(5, self.hb_seconds)
            self.fresh_mult = float(
                lm.get(
                    "fresh_window_multiplier", mon.get("fresh_window_multiplier", 2.0)
                )
            )
            self.fresh_mult = max(0.25, min(10.0, self.fresh_mult))

            srv = obj.get("server", {}) or {}
            self.selected_exe = srv.get("preferred_exe", "")
            backups = obj.get("backups", {}) or {}
            self.backups_enabled = bool(backups.get("enable", True))

        for k, v in list(self.paths.items()):
            self.paths[k] = str(v or "").strip()

    def _runtime_paths_v2(self) -> dict:
        rd = Path(self.paths.get("runtime_dir", "") or "")
        return {
            "runtime_dir": rd,
            "server_state": rd / "server_state.json",
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
            if os.name == "nt":
                now = time.monotonic()
                if now - self._last_tasklist_at < 1.0:
                    return True
                self._last_tasklist_at = now
                out = subprocess.check_output(
                    ["tasklist"], text=True, creationflags=CREATE_NO_WINDOW
                )
                needle = f" {pid} "
                return any(needle in (" " + line + " ") for line in out.splitlines())
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    def _hb_knobs(self) -> tuple[int, float]:
        # Config is captured when the worker is created. Never invoke a YAML
        # parser from this QRunnable: overlapping native/Python parser work has
        # caused fatal interpreter access violations on Windows.
        return self.hb_seconds, self.fresh_mult

    def _is_fresh(self, state_path: Path, hb_seconds: int, mult: float) -> bool:
        try:
            data = self._read_json(state_path)
            lu = (data.get("last_updated") or "").strip()
            if not lu:
                return False
            from datetime import datetime, timezone

            lu_norm = lu.replace("Z", "+00:00")
            dt = datetime.fromisoformat(lu_norm)
            if dt.tzinfo is None:
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

            ss = self._read_json(rp["server_state"])
            pid_txt = str(ss.get("pid", "") or "").strip()
            if not pid_txt:
                flag = self._read_json(rp["state_flag"])
                pid_txt = str(flag.get("pid", "") or "").strip()
            srv_on = self._pid_alive(pid_txt)

            lm_pid = self._read_text(rt["pid_log"])
            lm_on = self._pid_alive(lm_pid)
            lm_fresh = self._is_fresh(rt["state_log"], hb_seconds, fresh_mult)

            cm_pid = self._read_text(rt["pid_crash"])
            cm_on = self._pid_alive(cm_pid)
            cs = self._read_json(rt["state_crash"])
            if not cs:
                cs = self._read_json(rp.get("crash_state", rt["state_crash"]))
            mode = (
                (cs.get("status") or cs.get("mode") or "unknown") if cs else "unknown"
            )

            backup_state_path = rp["runtime_dir"] / "backup.state.json"
            bk = self._read_json(backup_state_path)

            snapshot_backup = {
                "enabled": self.backups_enabled,
                "last_utc": bk.get("last_utc"),
                "last_zip": bk.get("last_zip"),
                "counts": bk.get("counts") or {},
                "root": bk.get("root"),
            }

            snapshot = {
                "server": srv_on,
                "server_available": Path(str(self.selected_exe or "")).is_file(),
                "server_executable": str(self.selected_exe or ""),
                "logmon": lm_on,
                "logmon_fresh": lm_fresh,
                "crashmon": cm_on,
                "crash_mode": mode,
                "backup": snapshot_backup,
            }

            self.signals.ready.emit(snapshot)
        except Exception:
            pass
        finally:
            self.signals.finished.emit()
