# Controller/crash_monitor.py
#!/usr/bin/env python3
from __future__ import annotations

import json, os, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config_helper import config
from Tools.features import is_feature_enabled
from Tools.process import (
    current_headless_flag,
    find_running_server,
    is_server_running,
)
from Tools.discord import send_discord_message as send_discord
from Tools.state_io import write_state
from Tools.restart import initiate_controlled_restart
from Tools.runtime import (
    STATE_FLAG,
    is_shutdown_in_progress,
    startup_grace_active,
    autorestart_quiet_active,
)

_CRASH_CFG = dict(config.get("crash_monitor") or {})


def _crash_int(new_key: str, legacy_key: str, default: int) -> int:
    val = _CRASH_CFG.get(new_key)
    if val is None:
        val = config.get(legacy_key, default)
    try:
        return int(val)
    except Exception:
        return int(default)


# Cadence
MONITOR_INTERVAL_SEC = max(
    5, _crash_int("heartbeat_seconds", "crash_monitor_interval_seconds", 60)
)
IDLE_NOTIFY_MINUTES = _crash_int(
    "idle_notify_minutes", "crash_monitor_idle_notify_minutes", 15
)

# New, optional knobs (with safe defaults)
CRASH_NOTIFY_DEBOUNCE = _crash_int(
    "notify_debounce_seconds", "crash_notify_debounce_seconds", 300
)
BACKOFF_BASE = _crash_int("crash_backoff_base", "crash_backoff_base", 2)
BACKOFF_MAX_SECONDS = _crash_int(
    "crash_backoff_max_seconds", "crash_backoff_max_seconds", 900
)
BREAKER_MAX_ATTEMPTS = _crash_int(
    "crash_loop_max_attempts", "crash_loop_max_attempts", 5
)
BREAKER_WINDOW_MIN = _crash_int(
    "crash_loop_window_minutes", "crash_loop_window_minutes", 10
)
BREAKER_COOLDOWN_SEC = _crash_int(
    "crash_loop_cooldown_seconds", "crash_loop_cooldown_seconds", 600
)

# Runtime files
# PID_FILE    = Path(RUNTIME_DIR) / "crash_monitor.pid"
# STATE_FILE  = Path(RUNTIME_DIR) / "crash_monitor_state.json"
# STOP_FLAG   = Path(RUNTIME_DIR) / "stop_crash_monitor.flag"
# RESTART_LOG = Path(RUNTIME_DIR) / "restart_state.json"
# BREAKER     = Path(RUNTIME_DIR) / "breaker.tripped"
# LAST_CRASH_NOTIFY = Path(RUNTIME_DIR) / "crash_notify.last"


def _rt() -> dict:
    base = Path(
        config.get("runtime_dir") or Path(__file__).parents[1] / "Runtime"
    ).expanduser()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return {
        "runtime": base,
        "pid": base / "crash_monitor.pid",
        # Primary flag name used by GUI:
        "stop": base / "stop_crash_monitor.flag",
        # Accept old name too (for compatibility):
        "stop_legacy": base / "crash_monitor.stop",
        # unified + legacy state files
        "state": base / "crash_monitor.state.json",
        "state_legacy": base / "crash_monitor_state.json",
        "restart_log": base / "restart_state.json",
        "breaker": base / "breaker.tripped",
        "last_notify": base / "crash_notify.last",
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _atomic_write_json(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _write_state_mode(mode: str, *, active=None, watching=None) -> None:
    r = _rt()
    now = _now().isoformat()

    # Unified crash_monitor.state.json
    payload = {
        "pid": os.getpid(),
        "last_updated": now,
        "mode": mode,
        "active": bool(
            active if active is not None else mode in ("startup", "watching")
        ),
        "watching_server": bool(
            watching if watching is not None else mode == "watching"
        ),
    }
    write_state(r["state"], payload)

    # Legacy crash_monitor_state.json
    legacy = {
        "ts": now,
        "mode": mode,
        "pid": os.getpid(),
        "headless": current_headless_flag(),
    }
    _atomic_write_json(r["state_legacy"], legacy)


def _write_pid() -> None:
    r = _rt()
    try:
        r["pid"].write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def _clear_pid_and_stopflag() -> None:
    r = _rt()
    for p in (r["pid"], r["stop"], r["stop_legacy"]):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def _debounced_crash_notify(msg: str) -> None:
    r = _rt()
    try:
        last = int(r["last_notify"].read_text(encoding="utf-8").strip() or "0")
    except Exception:
        last = 0
    now = int(time.time())
    if now - last >= CRASH_NOTIFY_DEBOUNCE:
        _send(msg)
        try:
            r["last_notify"].write_text(str(now), encoding="utf-8")
        except Exception:
            pass


def _send(msg: str) -> None:
    send_discord(msg, channel="crash_monitor")


def _running_server_exists() -> bool:
    """
    Guarded wrapper around find_running_server to prevent psutil issues
    from killing the monitor loop.
    """
    try:
        return find_running_server() is not None
    except Exception as exc:
        print(f"[CrashMon] Failed to enumerate server processes: {exc}")
        return False


# --- helper: did someone request we stop? (support both flag names) ---
def _stop_requested() -> bool:
    r = _rt()
    return r["stop"].exists() or r["stop_legacy"].exists()


def _append_attempt(backoff_sec: int) -> None:
    r = _rt()
    data = {}
    try:
        data = json.loads(r["restart_log"].read_text(encoding="utf-8"))
    except Exception:
        data = {}
    at = data.get("attempts", [])
    at.append(_now().isoformat())
    data["attempts"] = at[-100:]
    data["last_backoff_sec"] = backoff_sec
    _atomic_write_json(r["restart_log"], data)


def _count_attempts_in_window(minutes: int) -> int:
    r = _rt()
    try:
        data = json.loads(r["restart_log"].read_text(encoding="utf-8"))
        at = data.get("attempts", [])
    except Exception:
        return 0
    cutoff = _now() - timedelta(minutes=minutes)
    c = 0
    for iso in at:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                c += 1
        except Exception:
            pass
    return c


def _breaker_active() -> bool:
    r = _rt()
    br = r["breaker"]
    if not br.exists():
        return False
    try:
        until = int(br.read_text(encoding="utf-8").strip() or "0")
        if int(time.time()) < until:
            return True
    except Exception:
        pass
    try:
        br.unlink(missing_ok=True)
    except Exception:
        pass
    return False


def _trip_breaker() -> None:
    r = _rt()
    until = int(time.time()) + BREAKER_COOLDOWN_SEC
    try:
        r["breaker"].write_text(str(until), encoding="utf-8")
    except Exception:
        pass
    _send(f"⚠️ Crash loop detected — breaker tripped for {BREAKER_COOLDOWN_SEC}s.")


def _next_backoff(prev: int) -> int:
    if prev <= 0:
        back = 1
    else:
        back = min(BACKOFF_MAX_SECONDS, prev * BACKOFF_BASE)
    return back


def main() -> None:
    if not is_feature_enabled("enable_crash_monitor"):
        print("[CrashMon] Disabled via config; exiting.")
        return

    print("[CrashMon] Starting crash monitor…")
    _send("🟢 Crash monitor started.")
    _write_pid()
    _write_state_mode("startup", active=True, watching=False)

    last_idle_notice_at = None
    announced_watching = False
    missing_count = 0
    backoff = 0

    while True:

        if _stop_requested():
            _send("🛑 Crash monitor stop requested; exiting.")
            _write_state_mode("stopped", active=False, watching=False)
            _clear_pid_and_stopflag()
            return

        # live disable
        if not is_feature_enabled("enable_crash_monitor"):
            _write_state_mode("disabled", active=False, watching=False)
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # intentional shutdown
        if is_shutdown_in_progress():
            _write_state_mode("intentional_shutdown", active=True, watching=False)
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # breaker
        if _breaker_active():
            _write_state_mode("breaker_cooldown", active=True, watching=False)
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # determine server state
        flag_present = STATE_FLAG.exists()
        process_running = is_server_running()

        if not flag_present:
            _write_state_mode("idle", active=True, watching=False)
            backoff = 0
            missing_count = 0
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        if process_running:
            _write_state_mode("watching", active=True, watching=True)
            if not announced_watching:
                _send("🧭 Crash monitor active: watching for unexpected exit.")
                announced_watching = True
            backoff = 0
            missing_count = 0
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # transient double-check: if we see it again, revert to watching
        if _running_server_exists():
            _write_state_mode("watching", active=True, watching=True)
            missing_count = 0
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # count consecutive misses before declaring a crash
        missing_count += 1
        if missing_count < 2:
            _write_state_mode("watching", active=True, watching=True)
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # now treat as real crash
        _write_state_mode("restart_pending", active=True, watching=False)

        # Respect quiet windows
        if startup_grace_active(180) or autorestart_quiet_active():
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Crash-loop protection
        if _count_attempts_in_window(BREAKER_WINDOW_MIN) >= BREAKER_MAX_ATTEMPTS:
            _trip_breaker()
            time.sleep(MONITOR_INTERVAL_SEC)
            continue

        # Exponential backoff before attempting restart
        backoff = _next_backoff(backoff)
        sleep_for = min(backoff, BACKOFF_MAX_SECONDS)
        time.sleep(sleep_for)

        # Debounced notification + controlled restart
        _debounced_crash_notify("❌ Crash detected. Attempting controlled restart…")
        ok = initiate_controlled_restart(reason="proc_missing")  # ← only once
        if ok:
            _send("🔄 Auto-restart initiated by crash monitor.")
            _append_attempt(sleep_for)  # ← use the actual backoff we slept
            backoff = 0
            missing_count = 0
            time.sleep(int(config.get("restart_settle_seconds", 5)))
        else:
            # already restarting or throttled — don’t count as attempt
            time.sleep(MONITOR_INTERVAL_SEC)
            continue


if __name__ == "__main__":
    try:
        main()
    finally:
        _clear_pid_and_stopflag()
